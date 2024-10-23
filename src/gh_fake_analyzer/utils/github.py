import os
import logging
import shutil
import git
from typing import List, Dict, Tuple, Optional
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
    
    def extract_commit_messages(self, commits_data: Dict[str, List[Dict]]) -> Dict[str, List[str]]:
        """Extract commit messages from commits data."""
        return {
            repo: [commit["commit"]["message"] for commit in commits]
            for repo, commits in commits_data.items()
        }
    
    def _fetch_single_repo_commits(self, username: str, repo_name: str, clone_url: str) -> Tuple[List[Dict], Optional[str]]:
        """Clone and fetch commits for a single repository."""
        repo_dir = os.path.join(self.user_dir, f"{username}_{repo_name}.git")
        
        try:
            logging.info(f"Git clone: {clone_url}")
            git.Repo.clone_from(clone_url, repo_dir, bare=CLONE_BARE, depth=CLONE_DEPTH)
            commits = self._get_commits_from_repo(repo_dir)
            return commits, None
            
        except git.exc.GitCommandError as e:
            logging.error(f"Git clone failed for {repo_name}: {e}")
            return [], str(e)
            
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