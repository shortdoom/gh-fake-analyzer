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
                    logging.error(
                        "Authentication required to monitor. Add GitHub token."
                    )
                    exit(1)
                elif response.status_code in [403, 429]:
                    cls._handle_rate_limit(response)
                    retry_count += 1
                    continue
                else:
                    logging.error(f"Request failed with status {response.status_code}.")
                    return None, None
            except requests.exceptions.RequestException as e:
                logging.error(f"An error occurred: {e}")
                return None, None

        return None, None

    @classmethod
    def _handle_rate_limit(cls, response, retry_count):
        if (
            "X-RateLimit-Remaining" in response.headers
            and response.headers["X-RateLimit-Remaining"] == "0"
        ):
            reset_time = int(response.headers["X-RateLimit-Reset"])
            sleep_time = max(0, reset_time - time.time())
            logging.warning(
                f"Primary rate limit exceeded. Sleeping for {sleep_time} seconds."
            )
            time.sleep(sleep_time + 1)
        elif "Retry-After" in response.headers:
            sleep_time = int(response.headers["Retry-After"])
            logging.warning(
                f"Secondary rate limit exceeded. Sleeping for {sleep_time} seconds."
            )
            time.sleep(sleep_time)
        else:
            sleep_time = int(pow(2, retry_count))
            logging.warning(
                f"Secondary rate limit exceeded. Retrying in {sleep_time} seconds."
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
