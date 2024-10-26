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
                        logging.info(f"Retry attempt {retry_count}/{cls.RETRY_LIMIT}")

                    wait_time = cls._handle_rate_limit(response.headers)
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error(f"Request failed with status {response.status_code}")
                    return None, None

            except requests.exceptions.RequestException as e:
                logging.error(f"Request error: {e}")
                return None, None

        logging.error(f"Exceeded retry limit ({cls.RETRY_LIMIT}) for URL: {url}")
        return None, None

    @classmethod
    def _handle_rate_limit(cls, headers):
        """
        Handle GitHub API rate limiting with proper timestamp handling.

        Args:
            response: The response from GitHub API
            retry_count: Number of retries attempted
        """
        # Check for secondary rate limit first
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
                wait_time = max(1, reset_time - current_time)
                logging.warning(
                    f"Rate limit exceeded. Waiting {wait_time} seconds until reset"
                )
                return wait_time
        except (ValueError, KeyError) as e:
            logging.debug(f"Error parsing rate limit headers: {e}")

        # Fallback to exponential backoff
        # /search has separate rate limit without enforcing it in the header
        logging.warning("Alternative endpoint rate limit. Waiting 30 seconds before retry.")
        return 30

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
