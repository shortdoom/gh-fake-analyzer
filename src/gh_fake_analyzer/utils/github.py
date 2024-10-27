import os
import logging
import shutil
import git
from typing import List, Dict, Tuple, Optional
from .api import APIUtils
from .config import CLONE_DEPTH, CLONE_BARE, REMOVE_REPO
from dataclasses import dataclass

@dataclass
class GitCommit:
    sha: str
    author_name: str
    author_email: str
    author_date: str
    committer_name: str
    committer_email: str
    committer_date: str
    message: str

    def to_dict(self) -> Dict:
        return {
            "sha": self.sha,
            "commit": {
                "author": {
                    "name": self.author_name,
                    "email": self.author_email,
                    "date": self.author_date,
                },
                "committer": {
                    "name": self.committer_name,
                    "email": self.committer_email,
                    "date": self.committer_date,
                },
                "message": self.message,
            },
        }

class GitCloneManager:
    def __init__(self, user_dir):
        self.user_dir = user_dir
        self.api_utils = APIUtils()

    def _get_token_from_headers(self):
        """Extract token from APIUtils headers if it exists."""
        auth_header = self.api_utils.HEADERS.get("Authorization", "")
        if auth_header.startswith("token "):
            return auth_header.split("token ")[1]
        return None

    def _get_clone_url(self, url: str) -> str:
        """Add token to URL if available."""
        token = self._get_token_from_headers()
        if token and url.startswith('https://'):
            return url.replace('https://', f'https://{token}@')
        return url

    def fetch_repository_commits(self, username: str, repositories: List[Dict]) -> Tuple[Dict[str, List[Dict]], List[Dict]]:
        """Fetch commits from repositories using git clone."""
        commits_data = {}
        failed_repos = []
        
        for repo in repositories:
            if not repo["fork"]:
                repo_name = repo["name"]
                clone_url = repo["clone_url"]
                repo_commits, error = self._fetch_single_repo_commits(username, repo_name, clone_url)
                
                if error:
                    failed_repos.append({
                        "repo_name": repo_name,
                        "clone_url": clone_url,
                        "reason": error,
                    })
                else:
                    commits_data[repo_name] = repo_commits
                    
        return commits_data, failed_repos
    
    def _fetch_single_repo_commits(self, username: str, repo_name: str, clone_url: str) -> Tuple[List[Dict], Optional[str]]:
        """Clone and fetch commits for a single repository."""
        repo_dir = os.path.join(self.user_dir, f"{username}_{repo_name}.git")
        
        try:
            # Set up environment to prevent interactive prompts
            env = os.environ.copy()
            env['GIT_TERMINAL_PROMPT'] = '0'
            env['GIT_SSH_COMMAND'] = 'ssh -o BatchMode=yes'
            
            # Get URL (with token if available)
            auth_url = self._get_clone_url(clone_url)
            
            # Log the public URL, not the authenticated one
            logging.info(f"Git clone: {clone_url}")
            
            # Attempt to clone
            git.Repo.clone_from(
                auth_url,
                repo_dir,
                bare=CLONE_BARE,
                depth=CLONE_DEPTH,
                env=env
            )
            
            commits = self._get_commits_from_repo(repo_dir)
            return commits, None
            
        except git.exc.GitCommandError as e:
            error_msg = str(e)
            if "Repository unavailable due to DMCA takedown" in error_msg:
                msg = f"Repository {repo_name} is unavailable due to DMCA takedown"
            elif "Authentication failed" in error_msg:
                # For authentication failures, try without token if it was used
                if self._get_token_from_headers() and auth_url != clone_url:
                    try:
                        logging.info(f"Retrying clone without authentication for {repo_name}")
                        git.Repo.clone_from(
                            clone_url,  # Use original URL without token
                            repo_dir,
                            bare=CLONE_BARE,
                            depth=CLONE_DEPTH,
                            env=env
                        )
                        commits = self._get_commits_from_repo(repo_dir)
                        return commits, None
                    except git.exc.GitCommandError as e2:
                        msg = f"Git clone failed with and without authentication for {repo_name}"
                else:
                    msg = f"Git clone failed for {repo_name}"
            else:
                msg = f"Git clone failed: {error_msg}"
            logging.error(msg)
            return [], msg
            
        finally:
            if os.path.exists(repo_dir) and REMOVE_REPO:
                shutil.rmtree(repo_dir)

    def _get_commits_from_repo(self, repo_dir: str) -> List[Dict]:
        """Get commits from a git repository."""
        try:
            repo = git.Repo(repo_dir)
            return [
                self._format_commit(commit).to_dict()
                for commit in repo.iter_commits()
            ]
        except Exception as e:
            logging.error(f"Error getting commits: {e}")
            return []
    
    def _format_commit(self, commit) -> GitCommit:
        """Format a git commit object into a GitCommit dataclass."""
        return GitCommit(
            sha=commit.hexsha,
            author_name=commit.author.name,
            author_email=commit.author.email,
            author_date=commit.authored_datetime.isoformat(),
            committer_name=commit.committer.name,
            committer_email=commit.committer.email,
            committer_date=commit.committed_datetime.isoformat(),
            message=commit.message
        )