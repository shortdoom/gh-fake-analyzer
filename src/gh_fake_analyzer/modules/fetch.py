import logging
from typing import List, Dict, Tuple, Optional
from ..utils.api import APIUtils
from ..utils.config import MAX_FOLLOWING, MAX_FOLLOWERS, MAX_REPOSITORIES

class FetchFromGithub:
    def __init__(self, api_utils: APIUtils):
        self.api_utils = api_utils
        
    def fetch_profile_data(self, username: str) -> Dict:
        """Fetch basic profile information for a user."""
        url = f"{self.api_utils.GITHUB_API_URL}/users/{username}"
        data, _ = self.api_utils.github_api_request(url)
        return data
        
    def fetch_following(self, username: str, limit: Optional[int] = None) -> List[Dict]:
        """Fetch list of users that the given user follows."""
        url = f"{self.api_utils.GITHUB_API_URL}/users/{username}/following"
        return self.api_utils.fetch_all_pages(
            url, 
            {"per_page": self.api_utils.ITEMS_PER_PAGE}, 
            limit=MAX_FOLLOWING
        )
        
    def fetch_followers(self, username: str, limit: Optional[int] = None) -> List[Dict]:
        """Fetch list of users following the given user."""
        url = f"{self.api_utils.GITHUB_API_URL}/users/{username}/followers"
        return self.api_utils.fetch_all_pages(
            url, 
            {"per_page": self.api_utils.ITEMS_PER_PAGE}, 
            limit=MAX_FOLLOWERS
        )
        
    def fetch_repositories(self, username: str, limit: Optional[int] = None) -> List[Dict]:
        """Fetch repositories for a user."""
        url = f"{self.api_utils.GITHUB_API_URL}/users/{username}/repos"
        return self.api_utils.fetch_all_pages(
            url, 
            {"per_page": self.api_utils.ITEMS_PER_PAGE}, 
            limit=MAX_REPOSITORIES
        )
        
    def fetch_repository_contributors(self, username: str, repo_name: str) -> List[Dict]:
        """Fetch contributors for a specific repository."""
        url = f"{self.api_utils.GITHUB_API_URL}/repos/{username}/{repo_name}/contributors"
        return self.api_utils.fetch_all_pages(url)
        
    def fetch_user_events(self, username: str, etag: Optional[str] = None) -> Tuple[List[Dict], Optional[str], int]:
        """Fetch events for a user with optional ETag for caching."""
        url = f"{self.api_utils.GITHUB_API_URL}/users/{username}/events"
        events, headers = self.api_utils.github_api_request(url, etag=etag)
        new_etag = headers.get("ETag") if headers else None
        poll_interval = int(headers.get("X-Poll-Interval", 60)) if headers else 60
        return events, new_etag, poll_interval
        
    def search_pull_requests(self, username: str) -> List[Dict]:
        """Search for pull requests by a user."""
        search_url = f"{self.api_utils.GITHUB_API_URL}/search/issues"
        search_params = {
            "q": f"type:pr author:{username}",
            "per_page": self.api_utils.ITEMS_PER_PAGE,
        }
        return self.api_utils.fetch_all_pages(search_url, search_params)
        
    def search_commits(self, username: str = None, message: str = None) -> List[Dict]:
        """Search for commits by a user or by commit message."""
        search_url = f"{self.api_utils.GITHUB_API_URL}/search/commits"
        query = []
        
        if username:
            query.append(f"author:{username}")
        
        if message:
            query.append(message)
            
        search_params = {
            "q": " ".join(query),
            "per_page": self.api_utils.ITEMS_PER_PAGE,
        }
        return self.api_utils.fetch_all_pages(search_url, search_params)

