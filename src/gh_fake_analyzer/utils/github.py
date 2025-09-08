import os
import logging
import shutil
import git
import time
from typing import List, Dict, Tuple, Optional
from .api import APIUtils
from ..modules.fetch import GithubFetchManager
from .config import CLONE_DEPTH, CLONE_BARE, REMOVE_REPO
from .concurrent import ConcurrentExecutor
from dataclasses import dataclass, field


@dataclass
class GitCommit:
    sha: str
    author_name: str
    author_email: str
    date: str  # Single date for both author and committer
    committer_name: str
    committer_email: str
    message: str
    owner: str = ""  # Repository owner
    pull_request: str = ""  # PR number if applicable

    def to_dict(self) -> Dict:
        return {
            "sha": self.sha,
            "owner": self.owner,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "committer_name": self.committer_name,
            "committer_email": self.committer_email,
            "date": self.date,
            "message": self.message,
            "pull_request": self.pull_request
        }


class GitProgressHandler(git.RemoteProgress):
    def __init__(self, repo_name: str):
        super().__init__()
        self.repo_name = repo_name
        self.last_update = 0
        self.update_interval = 5  # seconds between updates

    def update(self, op_code, cur_count, max_count=None, message=''):
        current_time = time.time()
        if current_time - self.last_update >= self.update_interval:
            if max_count:
                percent = (cur_count / max_count) * 100
                logging.info(f"Cloning {self.repo_name}: {percent:.1f}% complete")
            else:
                logging.info(f"Cloning {self.repo_name}: {cur_count} objects received")
            self.last_update = current_time


class GitCloneManager:
    def __init__(self, user_dir):
        self.user_dir = user_dir
        self.api_utils = APIUtils()
        self.github_fetch = GithubFetchManager(self.api_utils)
        self.concurrent_executor = ConcurrentExecutor(max_workers=5)  # Limit concurrent operations

    def _get_token_from_headers(self):
        """Extract token from APIUtils headers if it exists."""
        auth_header = self.api_utils.HEADERS.get("Authorization", "")
        if auth_header.startswith("token "):
            return auth_header.split("token ")[1]
        return None

    def _get_clone_url(self, url: str) -> str:
        """Add token to URL if available."""
        token = self._get_token_from_headers()
        if token and url.startswith("https://"):
            return url.replace("https://", f"https://{token}@")
        return url

    def _format_commit(self, commit, owner: str = "") -> GitCommit:
        """Format a git commit object into a GitCommit dataclass."""
        return GitCommit(
            sha=commit.hexsha,
            author_name=commit.author.name,
            author_email=commit.author.email,
            date=commit.authored_datetime.isoformat(),
            committer_name=commit.committer.name,
            committer_email=commit.committer.email,
            message=commit.message,
            owner=owner
        )

    def _format_api_commit(self, commit_data: Dict, owner: str = "", pr_number: str = "") -> GitCommit:
        """Format an API commit response into a GitCommit dataclass."""
        return GitCommit(
            sha=commit_data.get("sha", ""),
            author_name=commit_data.get("commit", {}).get("author", {}).get("name", ""),
            author_email=commit_data.get("commit", {}).get("author", {}).get("email", ""),
            date=commit_data.get("commit", {}).get("author", {}).get("date", ""),
            committer_name=commit_data.get("commit", {}).get("committer", {}).get("name", ""),
            committer_email=commit_data.get("commit", {}).get("committer", {}).get("email", ""),
            message=commit_data.get("commit", {}).get("message", ""),
            owner=owner,
            pull_request=pr_number
        )

    def _get_commits_from_repo(self, repo_dir: str) -> List[Dict]:
        """Get all commits from a git repository with repository information."""
        try:
            repo = git.Repo(repo_dir)

            # Extract repository info from the remote URL
            remote_url = repo.remotes.origin.url
            repo_name = remote_url.split("/")[-1].replace(".git", "")
            owner = remote_url.split("/")[-2]

            commits = []
            for commit in repo.iter_commits():
                commit_obj = self._format_commit(commit, owner=owner)
                commits.append(commit_obj.to_dict())

            return commits
        except Exception as e:
            logging.error(f"Error getting commits: {e}")
            return []

    def fetch_repository_commits(
        self, username: str, repositories: List[Dict]
    ) -> Tuple[Dict[str, List[Dict]], List[Dict]]:
        """
        Fetch commits from repositories:
        - For owned repos: Use git clone to get full history
        - For forked/external repos: Use API to get user's commits and PRs
        
        Args:
            username (str): GitHub username
            repositories (List[Dict]): List of repository information
            
        Returns:
            Tuple[Dict[str, List[Dict]], List[Dict]]: Dictionary of commits by repository and list of failed repositories
        """
        commits_data = {}
        failed_repos = []
        
        # Split repositories into owned and forked
        owned_repos = [repo for repo in repositories if not repo["fork"] and repo["owner"]["login"] == username]
        other_repos = []
        
        # Include both forked repos and repos where user contributed
        forked_repos = [repo for repo in repositories if repo["fork"]]
        other_repos.extend(forked_repos)
        
        # Search for external contributions (PRs and commits to other repos)
        try:
            # Search for PRs by the user
            pr_results = self.github_fetch.search_pull_requests(username)
            if pr_results:
                # Group PRs by repository
                pr_by_repo = {}
                for pr in pr_results:
                    if not pr or "repository_url" not in pr:
                        continue
                        
                    repo_full_name = pr["repository_url"].split("/")[-2:]
                    if len(repo_full_name) < 2:
                        continue
                        
                    repo_owner = repo_full_name[0]
                    repo_name = repo_full_name[1]
                    
                    # Skip if it's user's own repository
                    if repo_owner == username:
                        continue
                        
                    repo_key = f"{repo_owner}/{repo_name}"
                    if repo_key not in pr_by_repo:
                        pr_by_repo[repo_key] = []
                    pr_by_repo[repo_key].append(pr)
                    
                # For each repository with PRs, fetch the commits
                for repo_key, prs in pr_by_repo.items():
                    repo_owner, repo_name = repo_key.split("/")
                    repo_commits = []
                    
                    for pr in prs:
                        if not pr or "number" not in pr:
                            continue
                            
                        pr_commits = self.github_fetch.fetch_pull_request_commits(
                            repo_owner,
                            repo_name,
                            pr["number"]
                        )
                        
                        if pr_commits:
                            for commit in pr_commits:
                                if not commit or "author" not in commit or not commit["author"]:
                                    continue
                                    
                                if commit.get("author", {}).get("login") == username:
                                    commit_obj = self._format_api_commit(commit)
                                    commit_dict = commit_obj.to_dict()
                                    commit_dict["owner"] = repo_owner
                                    commit_dict["pull_request"] = str(pr["number"])
                                    repo_commits.append(commit_dict)
                    
                    if repo_commits:
                        commits_data[repo_name] = repo_commits
            
            # Search for direct commits (not through PRs)
            commit_results = self.github_fetch.search_commits(username)
            if commit_results:
                for commit in commit_results:
                    if not commit or "repository" not in commit:
                        continue
                        
                    repo = commit["repository"]
                    if not repo or "name" not in repo or "owner" not in repo:
                        continue
                        
                    repo_name = repo["name"]
                    repo_owner = repo["owner"].get("login")
                    
                    if not repo_owner:
                        continue
                    
                    # Skip if it's user's own repository or we already have this repo's commits
                    if repo_owner == username or repo_name in commits_data:
                        continue
                    
                    # Get full commit details
                    commit_data = self.github_fetch.fetch_commit_author(
                        repo_owner,
                        repo_name,
                        commit.get("sha", "")
                    )
                    
                    if commit_data:
                        if repo_name not in commits_data:
                            commits_data[repo_name] = []
                        
                        commit_obj = self._format_api_commit(commit_data)
                        commit_dict = commit_obj.to_dict()
                        commit_dict["owner"] = repo_owner
                        commit_dict["pull_request"] = ""
                        commits_data[repo_name].append(commit_dict)
                        
        except Exception as e:
            logging.error(f"Error fetching external contributions for {username}: {e}")
        
        # Process owned repositories with git clone
        clone_results = self.concurrent_executor.run_concurrent(
            self._fetch_single_repo_commits,
            [(repo, username) for repo in owned_repos]
        )
        
        # Process clone results
        for result in clone_results:
            if result:
                repo_name, commits, error = result
                if error:
                    failed_repos.append(error)
                elif commits:
                    commits_data[repo_name] = commits
        
        # Process forked repositories via API
        for repo in other_repos:
            try:
                repo_name = repo["name"]
                repo_owner = repo["owner"]["login"]
                
                # Skip if we already have this repo's commits from PR/commit search
                if repo_name in commits_data:
                    continue
                
                # Search for user's commits in this repository
                search_url = f"{self.api_utils.GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/commits"
                params = {"author": username}
                commits_response, _ = self.api_utils.github_api_request(search_url, params)
                
                if commits_response:
                    commits = []
                    for commit in commits_response:
                        commit_obj = self._format_api_commit(commit)
                        commit_dict = commit_obj.to_dict()
                        commit_dict["owner"] = repo_owner
                        commit_dict["pull_request"] = ""
                        commits.append(commit_dict)
                        
                    if commits:
                        commits_data[repo_name] = commits
                        
            except Exception as e:
                logging.error(f"Error fetching commits for repository {repo_name}: {e}")
                failed_repos.append({
                    "repo_name": repo_name,
                    "clone_url": repo.get("clone_url"),
                    "reason": f"Failed to fetch commits via API: {str(e)}"
                })

        return commits_data, failed_repos

    def _fetch_single_repo_commits(
        self, args: Tuple[Dict, str]
    ) -> Tuple[str, List[Dict], Optional[Dict]]:
        """
        Clone and fetch commits from a single repository.

        Args:
            args (Tuple[Dict, str]): Tuple of (repository information, username)

        Returns:
            Tuple[str, List[Dict], Optional[Dict]]: Repo name, list of commits, and error if any
        """
        repo, username = args
        repo_name = repo["name"]
        repo_dir = os.path.join(self.user_dir, f"{username}_{repo_name}.git")

        try:
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"

            auth_url = self._get_clone_url(repo["clone_url"])
            logging.info(f"Starting clone of {repo_name}")

            git.Repo.clone_from(
                auth_url, 
                repo_dir, 
                bare=CLONE_BARE, 
                depth=CLONE_DEPTH, 
                env=env,
                progress=GitProgressHandler(repo_name)
            )

            try:
                repo_obj = git.Repo(repo_dir)
                commits = []

                for commit in repo_obj.iter_commits():
                    commit_obj = self._format_commit(
                        commit,
                        owner=repo["owner"]["login"]
                    )
                    commits.append(commit_obj.to_dict())

                return repo_name, commits, None

            except Exception as e:
                logging.error(f"Error getting commits for {repo_name}: {e}")
                return repo_name, [], {
                    "repo_name": repo_name,
                    "clone_url": repo["clone_url"],
                    "reason": str(e),
                }

        except git.exc.GitCommandError as e:
            error_msg = str(e)
            if "Repository unavailable due to DMCA takedown" in error_msg:
                msg = f"Repository {repo_name} is unavailable due to DMCA takedown"
            elif "Authentication failed" in error_msg:
                if self._get_token_from_headers() and auth_url != repo["clone_url"]:
                    try:
                        logging.info(f"Retrying clone without authentication for {repo_name}")
                        git.Repo.clone_from(
                            repo["clone_url"],
                            repo_dir,
                            bare=CLONE_BARE,
                            depth=CLONE_DEPTH,
                            env=env,
                        )
                        commits = self._get_commits_from_repo(repo_dir)
                        return repo_name, commits, None
                    except git.exc.GitCommandError as e2:
                        msg = f"Git clone failed with and without authentication for {repo_name}"
                else:
                    msg = f"Git clone failed for {repo_name}"
            else:
                msg = f"Git clone failed: {error_msg}"
            
            logging.error(msg)
            return repo_name, [], {
                "repo_name": repo_name,
                "clone_url": repo["clone_url"],
                "reason": msg,
            }

        finally:
            if os.path.exists(repo_dir) and REMOVE_REPO:
                shutil.rmtree(repo_dir)

    def extract_commit_messages(
        self, commits_data: Dict[str, List[Dict]]
    ) -> Dict[str, List[str]]:
        """Extract commit messages from commits data."""
        messages = {}
        try:
            for repo, commits in commits_data.items():
                messages[repo] = [commit["message"] for commit in commits]
        except Exception as e:
            logging.error(f"Error extracting commit messages: {e}")
            return {}
        return messages
