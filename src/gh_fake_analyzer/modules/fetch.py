import logging
import os
import requests
from typing import List, Dict, Tuple, Optional
from ..utils.api import APIUtils
from ..utils.config import MAX_FOLLOWING, MAX_FOLLOWERS, MAX_REPOSITORIES

class GithubFetchManager:
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

    def fetch_user_issues(self, username: str) -> List[Dict]:
        """
        Fetch all issues created by a user across GitHub.

        Args:
            username (str): GitHub username to fetch issues for

        Returns:
            List[Dict]: List of issues with repository name, date, title and URL
        """
        search_url = f"{self.api_utils.GITHUB_API_URL}/search/issues"
        search_params = {
            "q": f"author:{username} type:issue",
            "per_page": self.api_utils.ITEMS_PER_PAGE,
        }

        raw_issues = self.api_utils.fetch_all_pages(search_url, search_params)

        # Process and clean up the issue data
        cleaned_issues = []
        for issue in raw_issues:
            # Extract repo name from repository_url (format: ".../repos/owner/repo")
            repo_parts = issue["repository_url"].split("/")
            repo_name = f"{repo_parts[-2]}/{repo_parts[-1]}"

            cleaned_issues.append({
                "repo": repo_name,
                "created_at": issue["created_at"],
                "title": issue["title"],
                "url": issue["html_url"].replace("https://github.com", ""),
                "body": issue["body"],
                "state": issue["state"],
                "number": issue["number"]
            })

        return cleaned_issues
    
    def fetch_issue_comments(self, repo_owner: str, repo_name: str, issue_number: int) -> List[Dict]:
        """
        Fetch comments for a specific issue.
        Handles the direct array response from the API.
        """
        url = f"{self.api_utils.GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/issues/{issue_number}/comments"
        comments, _ = self.api_utils.github_api_request(url)
        return comments if comments else []

    def fetch_user_issue_comments(self, username: str) -> List[Dict]:
        """
        Fetch all comments made by a user on issues across GitHub.
        
        Args:
            username (str): GitHub username to fetch comments for
            
        Returns:
            List[Dict]: List of comments with repository name, issue info, and comment details
        """
        search_url = f"{self.api_utils.GITHUB_API_URL}/search/issues"
        search_params = {
            "q": f"commenter:{username} type:issue",
            "per_page": self.api_utils.ITEMS_PER_PAGE,
        }
        
        raw_issues = self.api_utils.fetch_all_pages(search_url, search_params)
        
        cleaned_comments = []
        for issue in raw_issues:
            # Get repo info
            repo_parts = issue["repository_url"].split("/")
            repo_owner = repo_parts[-2]
            repo_name = repo_parts[-1]
            
            # Fetch comments for this specific issue using direct request
            comments = self.fetch_issue_comments(repo_owner, repo_name, issue["number"])
            
            # Filter for comments by our user and clean the data
            for comment in comments:
                if comment["user"]["login"].lower() == username.lower():
                    cleaned_comments.append({
                        "repo": f"{repo_owner}/{repo_name}",
                        "issue_title": issue["title"],
                        "issue_number": issue["number"],
                        "issue_url": issue["html_url"].replace("https://github.com", ""),
                        "comment_url": comment["html_url"].replace("https://github.com", ""),
                        "comment_id": comment["id"],
                        "created_at": comment["created_at"],
                        "updated_at": comment["updated_at"],
                        "body": comment["body"],
                    })
        
        return cleaned_comments
    
    def download_avatar(self, avatar_url: str, save_path: str) -> Optional[str]:
        """
        Download user's avatar from GitHub and save it locally.
        
        Args:
            avatar_url (str): URL of the avatar to download
            save_path (str): Directory path where to save the avatar
            
        Returns:
            Optional[str]: Name of the saved avatar file or None if download failed
        """
        try:
            if not avatar_url:
                logging.warning("No avatar URL provided")
                return None
                
            # Determine file extension from URL (usually .png or .jpg)
            file_extension = "png"  # Default to png
            if "?" in avatar_url:
                avatar_url = avatar_url.split("?")[0]  # Remove URL parameters
            if "." in avatar_url.split("/")[-1]:
                file_extension = avatar_url.split(".")[-1]
                
            # Extract username from save_path
            username = os.path.basename(save_path)
            avatar_filename = f"{username}_avatar.{file_extension}"
            avatar_path = os.path.join(save_path, avatar_filename)
            
            # Download avatar using requests
            response = requests.get(avatar_url, stream=True)
            response.raise_for_status()
            
            with open(avatar_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            logging.info(f"Avatar saved to {avatar_path}")
            return avatar_filename
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Error downloading avatar: {e}")
            return None
        except IOError as e:
            logging.error(f"Error saving avatar: {e}")
            return None