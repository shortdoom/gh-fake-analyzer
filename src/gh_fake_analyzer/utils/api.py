import logging
import requests
import time
from typing import Dict, List, Optional, Tuple
import requests_cache
from .concurrent import ConcurrentExecutor


class APIUtils:
    GITHUB_API_URL = "https://api.github.com"
    BASE_GITHUB_URL = "https://github.com/"
    HEADERS = {"Accept": "application/vnd.github.v3+json"}
    RETRY_LIMIT = 10
    ITEMS_PER_PAGE = 100
    SLEEP_INTERVAL = 1
    CACHE_EXPIRY = 3600  # Cache for 1 hour
    MAX_CONCURRENT_REQUESTS = 5  # Limit concurrent API requests

    def __init__(self):
        self.concurrent_executor = ConcurrentExecutor(
            max_workers=self.MAX_CONCURRENT_REQUESTS, 
            api_batch_size=self.MAX_CONCURRENT_REQUESTS
        )
        # Initialize cache
        self.session = requests_cache.CachedSession(
            'github_cache',
            backend='sqlite',
            expire_after=self.CACHE_EXPIRY
        )

    @classmethod
    def set_token(cls, token):
        if token:
            cls.HEADERS["Authorization"] = f"token {token}"

    def github_api_request(self, url: str, params: Optional[Dict] = None, etag: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Make a GitHub API request with caching and rate limiting."""
        headers = self.HEADERS.copy()
        if etag:
            headers["If-None-Match"] = etag

        retry_count = 0
        while retry_count < self.RETRY_LIMIT:
            try:
                response = self.session.get(url, headers=headers, params=params)
                logging.info(f"Request URL: {response.url}")

                # First check response status
                if response.status_code == 304:
                    return None, response.headers
                elif response.status_code == 200:
                    return response.json(), response.headers
                elif response.status_code == 401:
                    logging.error("Authentication required. Add GitHub token.")
                    exit(1)
                elif response.status_code in [403, 429]:
                    retry_count += 1
                    if retry_count > 1:
                        logging.info(f"Retry attempt {retry_count}/{self.RETRY_LIMIT}")

                    wait_time = self._handle_rate_limit(response.headers)
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error(f"Request failed with status {response.status_code}")
                    return None, None

            except requests.exceptions.RequestException as e:
                logging.error(f"Request error: {e}")
                return None, None

        logging.error(f"Exceeded retry limit ({self.RETRY_LIMIT}) for URL: {url}")
        return None, None

    def _handle_rate_limit(self, headers: Dict) -> int:
        """
        Handle GitHub API rate limiting with proper timestamp handling.
        Search API: 30 requests/minute (1 request/2 seconds)
        Regular API: 5000 requests/hour (1 request/0.72 seconds)

        Args:
            headers: Response headers from GitHub API
        """
        # Check for secondary rate limit first (abuse detection)
        if "Retry-After" in headers:
            wait_time = int(headers["Retry-After"])
            logging.warning(f"Secondary rate limit hit. Waiting {wait_time} seconds")
            return wait_time

        # Check for primary rate limit
        try:
            if (
                headers.get("X-RateLimit-Remaining") == "0"
                and "X-RateLimit-Reset" in headers
            ):
                reset_time = int(headers["X-RateLimit-Reset"])
                current_time = int(time.time())

                # Special handling for Search API
                if headers.get("X-RateLimit-Resource") == "search":
                    wait_time = max(30, reset_time - current_time)
                    logging.warning(f"Search API rate limit hit. Waiting {wait_time} seconds.")
                    return wait_time

                # Regular API rate limit
                wait_time = max(1, reset_time - current_time)
                logging.warning(f"Rate limit exceeded. Waiting {wait_time} seconds until reset")
                return wait_time

            # Even if not at limit, add small delay for search API
            if headers.get("X-RateLimit-Resource") == "search":
                logging.warning("Search API request. Adding 30 second delay.")
                return 30

        except (ValueError, KeyError) as e:
            logging.debug(f"Error parsing rate limit headers: {e}")

        # Fallback delay based on endpoint type
        if "search" in headers.get("X-RateLimit-Resource", ""):
            logging.warning("Search API fallback. Adding 2 second delay.")
            return 2

        # Default minimum delay for regular API
        logging.warning("Regular API fallback. Adding 1 second delay.")
        return 1

    def fetch_all_pages(self, url: str, params: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        """Fetch all pages of results concurrently with rate limiting."""
        # Get first page to determine total pages
        first_page_params = params.copy() if params else {}
        first_page_params['per_page'] = self.ITEMS_PER_PAGE
        first_page_params['page'] = 1
        
        first_page, headers = self.github_api_request(url, first_page_params)
        if not first_page:
            return []
            
        results = []
        if isinstance(first_page, dict) and "items" in first_page:
            results.extend(first_page["items"])
        else:
            results.extend(first_page)
            
        # Check if we need more pages
        if limit and len(results) >= limit:
            return results[:limit]
            
        # Get total pages from Link header
        total_pages = 1
        if "Link" in headers:
            for link in requests.utils.parse_header_links(headers["Link"]):
                if link["rel"] == "last":
                    total_pages = int(link["url"].split("page=")[-1])
                    break
                    
        if total_pages > 1:
            # Prepare requests for remaining pages
            page_requests = []
            for page in range(2, total_pages + 1):
                page_params = params.copy() if params else {}
                page_params['per_page'] = self.ITEMS_PER_PAGE
                page_params['page'] = page
                page_requests.append({
                    'url': url,
                    'params': page_params
                })
                
            # Process pages in batches to respect rate limits
            all_results = []
            for i in range(0, len(page_requests), self.MAX_CONCURRENT_REQUESTS):
                batch = page_requests[i:i + self.MAX_CONCURRENT_REQUESTS]
                
                # Fetch batch concurrently
                batch_results = self.concurrent_executor.run_api_requests(
                    batch,
                    headers=self.HEADERS
                )
                
                # Process batch results
                for page_data in batch_results:
                    if page_data:
                        if isinstance(page_data, dict) and "items" in page_data:
                            all_results.extend(page_data["items"])
                        else:
                            all_results.extend(page_data)
                            
                        if limit and len(results) + len(all_results) >= limit:
                            results.extend(all_results)
                            return results[:limit]
                
                # Add delay between batches to avoid rate limiting
                if i + self.MAX_CONCURRENT_REQUESTS < len(page_requests):
                    time.sleep(2)  # 2 second delay between batches
                    
            results.extend(all_results)
                        
        return results[:limit] if limit else results

    @staticmethod
    def _get_next_url(headers: Dict) -> Optional[str]:
        """Extract next page URL from Link header."""
        if "Link" in headers:
            links = requests.utils.parse_header_links(headers["Link"])
            return next((link["url"] for link in links if link["rel"] == "next"), None)
        return None
