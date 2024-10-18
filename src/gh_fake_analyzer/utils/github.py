import os
import logging
import shutil
import git
from .config import CLONE_DEPTH

class GitManager:
    def __init__(self, username, user_dir):
        self.username = username
        self.user_dir = user_dir

    def clone_and_fetch_commits(self, repo):
        repo_name = repo["name"]
        clone_url = repo["clone_url"]
        repo_dir = os.path.join(self.user_dir, f"{self.username}_{repo_name}.git")

        try:
            print(f"Git clone: {clone_url}")
            git.Repo.clone_from(clone_url, repo_dir, bare=True, depth=CLONE_DEPTH)
            commits = self.fetch_repo_commits(repo_dir)
            return repo_name, commits
        except git.exc.GitCommandError as e:
            logging.error(f"Git clone failed for {repo_name}: {e}")
            return repo_name, {"error": str(e)}
        finally:
            if os.path.exists(repo_dir):
                shutil.rmtree(repo_dir)

    def fetch_repo_commits(self, repo_dir):
        try:
            repo = git.Repo(repo_dir)
            return [self._format_commit(commit) for commit in repo.iter_commits()]
        except Exception as e:
            logging.error(f"fetch_repo_commits() Error: {e}")
            return []

    def _format_commit(self, commit):
        return {
            "sha": commit.hexsha,
            "commit": {
                "author": {
                    "name": commit.author.name,
                    "email": commit.author.email,
                    "date": commit.authored_datetime.isoformat(),
                },
                "committer": {
                    "name": commit.committer.name,
                    "email": commit.committer.email,
                    "date": commit.committed_datetime.isoformat(),
                },
                "message": commit.message,
            },
        }