import logging
from typing import Dict, List, Any
from dateutil import parser
import requests
from .fetch import GithubFetchManager
from ..utils.data import POPULAR_COMMIT_MESSAGES

class GitHubDataFilter:
    """Comparative analysis filters for potential fake Github profiles"""
    
    def __init__(self, github_fetch: GithubFetchManager):
        self.github_fetch = github_fetch
        
    def filter_by_creation_date(
        self, 
        commits_data: Dict[str, List[Dict]], 
        account_created_at: str
    ) -> List[Dict]:
        """
        Filter repositories where first commit predates account creation.
        
        Args:
            commits_data: Dictionary of repository commits
            account_created_at: ISO format date string of account creation
            
        Returns:
            List of repositories with suspicious commit dates
        """
        account_date = parser.parse(account_created_at)
        date_filter = []
        
        for repo_name, commits in commits_data.items():
            if commits:
                first_commit_date = parser.parse(
                    commits[-1]["commit"]["author"]["date"]
                )
                if first_commit_date < account_date:
                    date_filter.append({
                        "repo": repo_name,
                        "reason": "account creation date later than the first commit to the repository",
                        "commit_date": first_commit_date.isoformat(),
                    })
                    
        return date_filter
        
    def filter_commits_by_similarity(
        self, 
        commits_data: Dict[str, List[Dict]]
    ) -> List[Dict]:
        """
        Filter repository commits by searching for similar (copied) commit messages across GitHub.
        
        Args:
            commits_data: Dictionary of repository commits
            
        Returns:
            List of commits with matching messages in other repositories
        """
        commit_filter = []
        
        for repo_name, commits in commits_data.items():
            if commits:
                filtered_commits = self._process_repo_commits(repo_name, commits)
                commit_filter.extend(filtered_commits)
            else:
                commit_filter.append({
                    "target_repo": repo_name,
                    "target_commit": "No commits found",
                    "search_results": 0,
                    "matching_repos": [],
                })
                
        return commit_filter
    
    def _process_repo_commits(
        self, 
        repo_name: str, 
        commits: List[Dict]
    ) -> List[Dict]:
        """
        Process commits from a single repository for filtering.
        Checks all commits for similarity matches.
        """
        filtered_commits = []
        
        for commit in commits:
            commit_message = commit["commit"]["message"]
            if self._valid_target_search(commit_message):
                cleaned_message = self._clean_commit_message(commit_message)
                search_result = self._search_similar_commits(
                    repo_name, 
                    cleaned_message
                )
                if search_result is not None:
                    filtered_commits.append(search_result)
                    logging.info(
                        f"Found {search_result['search_results']} matches for commit in {repo_name}: "
                        f"{commit_message[:100]}..."
                    )
            else:
                logging.info(f"Not valid commit {commit_message}")
                    
        return filtered_commits
    
    def _search_similar_commits(
        self, 
        repo_name: str, 
        commit_message: str
    ) -> Dict[str, Any]:
        """Search for similar commit messages across GitHub."""
        try:
            search_url = f"{self.github_fetch.api_utils.GITHUB_API_URL}/search/commits"
            search_params = {
                "q": commit_message,
                "per_page": self.github_fetch.api_utils.ITEMS_PER_PAGE,
            }
            
            search_results, _ = self.github_fetch.api_utils.github_api_request(
                search_url, 
                params=search_params
            )
            
            if not search_results:
                return None
                
            total_count = search_results.get("total_count", 0)
            if total_count > 0:
                matching_repos = [
                    item["repository"]["html_url"].replace(
                        "https://github.com/", ""
                    )
                    for item in search_results["items"]
                    if item.get("repository", {}).get("html_url")
                ]
                
                if matching_repos:
                    return {
                        "target_repo": repo_name,
                        "target_commit": commit_message,
                        "search_results": total_count,
                        "matching_repos": matching_repos,
                    }
                    
        except requests.exceptions.HTTPError as e:
            logging.error(f"Error fetching search results for '{commit_message[:100]}...': {e}")
        except Exception as e:
            logging.error(f"Unexpected error searching commits: {e}")
            
        return None
    
    def _valid_target_search(self, message: str) -> bool:
        """Check if commit message length is within valid range."""
        cleaned_message = message.strip()
        return cleaned_message not in POPULAR_COMMIT_MESSAGES
    
    def _clean_commit_message(self, message: str) -> str:
        """Clean commit message by removing newlines."""
        return message.replace("\n", " ").replace("\r", " ")
