import logging
import os
import requests
from typing import List, Dict, Tuple, Optional
from ..utils.api import APIUtils
from ..utils.config import MAX_FOLLOWING, MAX_FOLLOWERS, MAX_REPOSITORIES
from urllib.parse import urlparse, parse_qs
from ..utils.concurrent import ConcurrentExecutor


class GithubFetchManager:
    def __init__(self, api_utils: APIUtils):
        self.api_utils = api_utils
        self.concurrent_executor = ConcurrentExecutor(max_workers=10)

    def fetch_profile_data(self, username: str) -> Dict:
        """Fetch basic profile information for a user."""
        url = f"{self.api_utils.GITHUB_API_URL}/users/{username}"
        data, _ = self.api_utils.github_api_request(url)
        return data

    def fetch_following(self, username: str, limit: Optional[int] = None) -> List[Dict]:
        """Fetch list of users that the given user follows."""
        url = f"{self.api_utils.GITHUB_API_URL}/users/{username}/following"
        return self.api_utils.fetch_all_pages(
            url, {"per_page": self.api_utils.ITEMS_PER_PAGE}, limit=MAX_FOLLOWING
        )

    def fetch_followers(self, username: str, limit: Optional[int] = None) -> List[Dict]:
        """Fetch list of users following the given user."""
        url = f"{self.api_utils.GITHUB_API_URL}/users/{username}/followers"
        return self.api_utils.fetch_all_pages(
            url, {"per_page": self.api_utils.ITEMS_PER_PAGE}, limit=MAX_FOLLOWERS
        )

    def fetch_repositories(
        self, username: str, limit: Optional[int] = None
    ) -> List[Dict]:
        """Fetch repositories for a user."""
        url = f"{self.api_utils.GITHUB_API_URL}/users/{username}/repos"
        return self.api_utils.fetch_all_pages(
            url, {"per_page": self.api_utils.ITEMS_PER_PAGE}, limit=MAX_REPOSITORIES
        )

    def fetch_repository_contributors(
        self, username: str, repo_name: str
    ) -> List[Dict]:
        """Fetch contributors for a specific repository."""
        url = (
            f"{self.api_utils.GITHUB_API_URL}/repos/{username}/{repo_name}/contributors"
        )
        return self.api_utils.fetch_all_pages(url)

    def fetch_user_received_events(
        self, username: str, etag: Optional[str] = None
    ) -> Tuple[List[Dict], Optional[str], int]:
        """Fetch events received by a user with optional ETag for caching."""
        url = f"{self.api_utils.GITHUB_API_URL}/users/{username}/received_events"
        events, headers = self.api_utils.github_api_request(url, etag=etag)
        new_etag = headers.get("ETag") if headers else None
        poll_interval = int(headers.get("X-Poll-Interval", 60)) if headers else 60
        return events or [], new_etag, poll_interval

    def fetch_user_events(
        self, username: str, etag: Optional[str] = None
    ) -> Tuple[List[Dict], Optional[str], int]:
        """Fetch events for a user with optional ETag for caching."""
        url = f"{self.api_utils.GITHUB_API_URL}/users/{username}/events"
        events, headers = self.api_utils.github_api_request(url, etag=etag)
        new_etag = headers.get("ETag") if headers else None
        poll_interval = int(headers.get("X-Poll-Interval", 60)) if headers else 60
        return events or [], new_etag, poll_interval

    def search_pull_requests(self, username: str) -> List[Dict]:
        """Search for pull requests by a user."""
        search_url = f"{self.api_utils.GITHUB_API_URL}/search/issues"
        search_params = {
            "q": f"type:pr author:{username}",
            "per_page": self.api_utils.ITEMS_PER_PAGE,
        }
        return self.api_utils.fetch_all_pages(search_url, search_params)

    def search_commits(self, username: str = None, message: str = None, repo: str = None) -> List[Dict]:
        """Search for commits by a user, message, or in a specific repo."""
        search_url = f"{self.api_utils.GITHUB_API_URL}/search/commits"
        query = []
        
        if username:
            query.append(f"author:{username}")
        
        if message:
            query.append(message)
            
        if repo:
            query.append(f"repo:{repo}")
            
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

            cleaned_issues.append(
                {
                    "repo": repo_name,
                    "created_at": issue["created_at"],
                    "title": issue["title"],
                    "url": issue["html_url"].replace("https://github.com", ""),
                    "body": issue["body"],
                    "state": issue["state"],
                    "number": issue["number"],
                }
            )

        return cleaned_issues

    def fetch_issue_comments(
        self, repo_owner: str, repo_name: str, issue_number: int
    ) -> List[Dict]:
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

        # Prepare requests for concurrent fetching
        comment_requests = []
        for issue in raw_issues:
            repo_parts = issue["repository_url"].split("/")
            repo_owner = repo_parts[-2]
            repo_name = repo_parts[-1]
            
            comment_requests.append({
                'url': f"{self.api_utils.GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/issues/{issue['number']}/comments",
                'issue_info': {
                    'repo': f"{repo_owner}/{repo_name}",
                    'title': issue['title'],
                    'number': issue['number'],
                    'html_url': issue['html_url']
                }
            })

        # Fetch comments concurrently
        comments_results = self.concurrent_executor.run_api_requests(
            comment_requests,
            headers=self.api_utils.HEADERS
        )

        # Process results
        cleaned_comments = []
        for i, comments in enumerate(comments_results):
            if comments:
                issue_info = comment_requests[i]['issue_info']
                for comment in comments:
                    if comment['user']['login'].lower() == username.lower():
                        cleaned_comments.append({
                            'repo': issue_info['repo'],
                            'issue_title': issue_info['title'],
                            'issue_number': issue_info['number'],
                            'issue_url': issue_info['html_url'].replace("https://github.com", ""),
                            'comment_url': comment['html_url'].replace("https://github.com", ""),
                            'comment_id': comment['id'],
                            'created_at': comment['created_at'],
                            'updated_at': comment['updated_at'],
                            'body': comment['body'],
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

            with open(avatar_path, "wb") as f:
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

    def search_users(self, search_query: str) -> List[Dict]:
        """
        Search for GitHub users using the GitHub Search API.

        Args:
            search_query (str): Search query string or full GitHub search URL

        Returns:
            List[Dict]: List of user search results
        """
        # Extract query if full GitHub URL is provided
        if "github.com/search" in search_query:
            parsed = urlparse(search_query)
            params = parse_qs(parsed.query)
            search_query = params.get("q", [""])[0]

        search_url = f"{self.api_utils.GITHUB_API_URL}/search/users"
        search_params = {"q": search_query, "per_page": self.api_utils.ITEMS_PER_PAGE}

        # The search API returns data in a different format with items key
        results = self.api_utils.fetch_all_pages(search_url, search_params)
        return results if isinstance(results, list) else results.get("items", [])
    
    def search_code(self, search_query: str) -> List[Dict]:
        """
        Search for content on GitHub using the GitHub Search API.
        This is a general search that will find the search term in any content.

        Args:
            search_query (str): Search query string or full GitHub search URL

        Returns:
            List[Dict]: List of search results
        """
        # Extract query if full GitHub URL is provided
        if "github.com/search" in search_query:
            parsed = urlparse(search_query)
            params = parse_qs(parsed.query)
            search_query = params.get("q", [""])[0]

        # Use the general search endpoint instead of /search/users
        search_url = f"{self.api_utils.GITHUB_API_URL}/search/code"
        search_params = {"q": search_query, "per_page": self.api_utils.ITEMS_PER_PAGE}

        # The search API returns data in a different format with items key
        results = self.api_utils.fetch_all_pages(search_url, search_params)
        return results if isinstance(results, list) else results.get("items", [])

    def fetch_commit_author(
        self, repo_owner: str, repo_name: str, commit_sha: str
    ) -> Optional[Dict]:
        """Fetch GitHub commit data to get author information.

        Args:
            repo_owner (str): Owner of the repository
            repo_name (str): Name of the repository
            commit_sha (str): Commit SHA to look up

        Returns:
            Optional[Dict]: Commit data containing author information if found
        """
        url = f"{self.api_utils.GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/commits/{commit_sha}"
        commit_data, _ = self.api_utils.github_api_request(url)
        return commit_data

    def search_pull_requests_by_commit(self, commit_sha: str) -> List[Dict]:
        """Search for pull requests containing a specific commit.
        
        Args:
            commit_sha (str): The commit SHA to search for
            
        Returns:
            List[Dict]: List of pull requests containing this commit
        """
        search_url = f"{self.api_utils.GITHUB_API_URL}/search/issues"
        search_params = {
            "q": f"type:pr {commit_sha}",
            "per_page": self.api_utils.ITEMS_PER_PAGE
        }
        
        results = self.api_utils.fetch_all_pages(search_url, search_params)
        return results if isinstance(results, list) else results.get("items", [])
        
    def fetch_pull_request_commits(self, owner: str, repo: str, pr_number: int) -> List[Dict]:
        """Fetch all commits from a specific pull request.
        
        Args:
            owner (str): Repository owner
            repo (str): Repository name
            pr_number (int): Pull request number
            
        Returns:
            List[Dict]: List of commits in the pull request
        """
        url = f"{self.api_utils.GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
        return self.api_utils.fetch_all_pages(url)

    def fetch_user_organizations(self, username: str) -> List[Dict]:
        """
        Fetch all organizations that a user is a member of.

        Args:
            username (str): GitHub username to fetch organizations for

        Returns:
            List[Dict]: List of organizations with their details
        """
        url = f"{self.api_utils.GITHUB_API_URL}/users/{username}/orgs"
        return self.api_utils.fetch_all_pages(url)

    def fetch_organization_members_count(self, org_name: str) -> Optional[int]:
        """
        Get the member count of a GitHub organization.

        Args:
            org_name (str): Name of the organization to get member count for

        Returns:
            Optional[int]: Number of members in the organization, or None if not found
        """
        url = f"{self.api_utils.GITHUB_API_URL}/orgs/{org_name}"
        org_data, _ = self.api_utils.github_api_request(url)
        return org_data.get("public_members_count") if org_data else None

    def check_user_relationships(self, username: str, target_usernames: List[str]) -> Dict[str, List[str]]:
        """
        Check if a user follows or has as a contributor any of the target usernames.

        Args:
            username (str): Username to check
            target_usernames (List[str]): List of usernames to check against

        Returns:
            Dict[str, List[str]]: Dictionary containing lists of usernames that are followed or contributors
        """
        result = {
            "following": [],
            "contributors": [],
            "fork_target_contributors": [],  # List of tuples (username, original_repo)
            # "target_repo_contributor": [],  # List of tuples (target_username, repo) where scanned user is contributor
            "fork_contributors": [],  # List of tuples (username, repo) where target users contributed to scanned user's fork
            "suspicious": "false"  # Flag indicating if the scanned username is in target_usernames
        }
        
        # Check if scanned username is in target_usernames
        if username.lower() in [target.lower() for target in target_usernames]:
            result["suspicious"] = "true"
        
        # Check following relationships
        following = self.fetch_following(username, limit=500)  # Limit to first 500 following
        following_usernames = {user["login"].lower() for user in following}
        result["following"] = [
            target for target in target_usernames 
            if target.lower() in following_usernames
        ]
        
        # Check contributors in user's repositories
        repos = self.fetch_repositories(username, limit=100)  # Limit to first 100 repos
        for repo in repos:
            # Skip if we can't access the repository
            if not repo.get("name"):
                continue
                
            try:
                # For forked repositories, check both original and fork contributors
                if repo.get("fork"):
                    if not repo.get("parent"):
                        continue
                    parent_owner = repo["parent"]["owner"]["login"]
                    parent_repo_name = repo["parent"]["name"]
                    
                    # Check contributors to the original repository
                    parent_contributors = self.fetch_repository_contributors(parent_owner, parent_repo_name)
                    parent_contributor_usernames = {
                        user["login"].lower() 
                        for user in parent_contributors 
                        if user["login"].lower() != parent_owner.lower()
                    }
                    
                    # Check contributors to the forked repository
                    fork_contributors = self.fetch_repository_contributors(username, repo["name"])
                    fork_contributor_usernames = {
                        user["login"].lower() 
                        for user in fork_contributors 
                        if user["login"].lower() != username.lower()
                    }
                    
                    # Add matching target usernames to appropriate lists
                    for target in target_usernames:
                        if target.lower() in parent_contributor_usernames:
                            result["fork_target_contributors"].append((target, f"{parent_owner}/{parent_repo_name}"))
                        if target.lower() in fork_contributor_usernames:
                            result["fork_contributors"].append((target, f"{username}/{repo['name']}"))
                            
                else:
                    # For non-forked repositories
                    owner = repo["owner"]["login"]
                    repo_name = repo["name"]
                    contributors = self.fetch_repository_contributors(owner, repo_name)
                    contributor_usernames = {
                        user["login"].lower() 
                        for user in contributors 
                        if user["login"].lower() != owner.lower()
                    }
                    
                    # Add matching target usernames to contributors list
                    for target in target_usernames:
                        if target.lower() in contributor_usernames:
                            result["contributors"].append(target)
                            
            except Exception as e:
                logging.error(f"Error fetching contributors for {owner}/{repo_name}: {e}")
                continue
        
        # TODO: Check if scanned user is a contributor to target users' repositories
        # This will be implemented later using database queries to avoid excessive API calls
        # for target in target_usernames:
        #     try:
        #         target_repos = self.fetch_repositories(target, limit=100)
        #         for repo in target_repos:
        #             if not repo.get("name"):
        #                 continue
        #             contributors = self.fetch_repository_contributors(target, repo["name"])
        #             contributor_usernames = {user["login"].lower() for user in contributors}
        #             if username.lower() in contributor_usernames:
        #                 result["target_repo_contributor"].append((target, f"{target}/{repo['name']}"))
        #     except Exception as e:
        #         logging.error(f"Error checking contributor status for {username} in {target}'s repositories: {e}")
        #         continue
        
        # Remove duplicates from contributors list
        result["contributors"] = list(set(result["contributors"]))
        
        return result