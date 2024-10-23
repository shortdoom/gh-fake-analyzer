import logging
import requests
import time

class APIUtils:
    GITHUB_API_URL = "https://api.github.com"
    BASE_GITHUB_URL = "https://github.com/"
    HEADERS = {"Accept": "application/vnd.github.v3+json"}
    RETRY_LIMIT = 10
    ITEMS_PER_PAGE = 100
    SLEEP_INTERVAL = 1

    @classmethod
    def set_token(cls, token):
        if token:
            cls.HEADERS["Authorization"] = f"token {token}"


    @classmethod
    def github_api_request(cls, url, params=None, etag=None):
        headers = cls.HEADERS.copy()
        if etag:
            headers["If-None-Match"] = etag

        retry_count = 0
        while retry_count < cls.RETRY_LIMIT:
            try:
                response = requests.get(url, headers=cls.HEADERS, params=params)
                logging.info(f"Request URL: {response.url}")

                if response.status_code == 304:
                    return None, response.headers
                elif response.status_code == 200:
                    return response.json(), response.headers
                elif response.status_code == 401:
                    logging.error("Authentication required. Add GitHub token.")
                    exit(1)
                elif response.status_code in [403, 429]:
                    if retry_count > 0:
                        logging.info(
                            f"Retry attempt {retry_count + 1}/{cls.RETRY_LIMIT} "
                            f"for rate limit"
                        )
                    cls._handle_rate_limit(response, retry_count)
                    retry_count += 1
                    continue
                else:
                    logging.error(
                        f"Request failed with status {response.status_code}"
                    )
                    return None, None
                    
            except requests.exceptions.RequestException as e:
                logging.error(f"Request error: {e}")
                return None, None

        logging.error(
            f"Exceeded retry limit ({cls.RETRY_LIMIT}) for URL: {url}"
        )
        return None, None

    @classmethod
    def _handle_rate_limit(cls, response, retry_count):
        """
        Handle GitHub API rate limiting with proper timestamp handling.
        
        Args:
            response: The response from GitHub API
            retry_count: Number of retries attempted
        """
        try:
            if "X-RateLimit-Remaining" in response.headers:
                remaining = int(response.headers.get("X-RateLimit-Remaining", "0"))
                reset_timestamp = int(response.headers.get("X-RateLimit-Reset", "0"))
                current_timestamp = int(time.time())
                
                if remaining == 0 and reset_timestamp > current_timestamp:
                    sleep_time = reset_timestamp - current_timestamp
                    reset_time_str = time.strftime(
                        '%Y-%m-%d %H:%M:%S', 
                        time.localtime(reset_timestamp)
                    )
                    
                    logging.warning(
                        f"Primary rate limit exceeded. Waiting {sleep_time} seconds "
                        f"until {reset_time_str}"
                    )
                    
                    if sleep_time > 0:
                        time.sleep(sleep_time + 1)  # Add 1 second buffer
                    return
                    
            if "Retry-After" in response.headers:
                sleep_time = int(response.headers["Retry-After"])
                logging.warning(
                    f"Secondary rate limit exceeded. Waiting {sleep_time} seconds "
                    f"as specified by GitHub."
                )
                time.sleep(sleep_time)
                return
                
            # Exponential backoff as fallback
            sleep_time = min(int(pow(2, retry_count)), 60)
            logging.warning(
                f"Rate limit encountered (attempt {retry_count + 1}/{cls.RETRY_LIMIT}). "
                f"Waiting {sleep_time} seconds."
            )
            time.sleep(sleep_time)
            
        except (ValueError, KeyError, TypeError) as e:
            # Fallback to exponential backoff if header parsing fails
            sleep_time = min(int(pow(2, retry_count)), 60)
            logging.warning(
                f"Error parsing rate limit headers ({str(e)}). "
                f"Using exponential backoff: {sleep_time} seconds"
            )
            time.sleep(sleep_time)
    
    @classmethod
    def fetch_all_pages(cls, url, params=None, limit=None):
        results = []
        while url and (limit is None or len(results) < limit):
            response, headers = cls.github_api_request(url, params)
            if response:
                new_items = (
                    response["items"]
                    if isinstance(response, dict) and "items" in response
                    else response
                )
                results.extend(
                    new_items[: limit - len(results)]
                    if limit is not None
                    else new_items
                )
                url = cls._get_next_url(headers)
                params = None
            else:
                break
        return results[:limit] if limit is not None else results

    @staticmethod
    def _get_next_url(headers):
        if "Link" in headers:
            links = requests.utils.parse_header_links(headers["Link"])
            return next((link["url"] for link in links if link["rel"] == "next"), None)
        return None
