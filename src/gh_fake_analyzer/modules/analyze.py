import logging
from ..utils.api import APIUtils
from ..utils.data import DataManager
from ..utils.github import GitCloneManager
from .fetch import GithubFetchManager
from .filter import GitHubDataFilter
from .monitor import GitHubMonitor


class GitHubProfileAnalyzer:
    def __init__(self, username, out_path=None):
        # Username to analyze
        self.username = username

        # Github API requests helper
        self.api_utils = APIUtils()

        # Local directories/files helper
        self.data_manager = DataManager(username, out_path)

        # Github git clone operations helper
        self.git_manager = GitCloneManager(self.data_manager.user_dir)

        # Github API data fetch helper
        self.github_fetch = GithubFetchManager(self.api_utils)

        # Local data additional filters
        self.data_filter = GitHubDataFilter(self.github_fetch)

        # Github event watcher application
        self.monitor = GitHubMonitor(self.api_utils)

        # Local data object initialization
        self.data = self.data_manager.load_existing() or {}

        logging.info(f"GitHubProfileAnalyzer initialized for {username}")
        logging.info(
            f"{'Found' if self.data else 'No'} data in {self.data_manager.report_file}"
        )

    def run_analysis(self):
        """Build required for generate_report() profile's data object"""
        try:
            self.fetch_profile_data()
            self.fetch_and_save_avatar()
            self.fetch_following()
            self.fetch_followers()
            self.fetch_profile_repos()
            self.fetch_from_git_clone()
            self.fetch_commit_messages()
            self.fetch_recent_events()
            self.fetch_user_issues()
            self.fetch_user_comments()
            self.filter_created_at()
            logging.info(f"Analysis completed for {self.username}")
        except Exception as e:
            logging.error(f"Error in run_analysis for {self.username}: {e}")

    def fetch_profile_data(self):
        """Fetch basic github profile data of a user."""
        self.data["profile_data"] = self.github_fetch.fetch_profile_data(self.username)

    def fetch_following(self):
        """Fetch all accounts user follows."""
        self.data["following"] = self.github_fetch.fetch_following(
            self.username,
        )

    def fetch_followers(self):
        """Fetch all followers of user."""
        self.data["followers"] = self.github_fetch.fetch_followers(
            self.username,
        )

    def fetch_profile_repos(self):
        """Fetch all user's repository data."""
        self.data["repos"] = self.github_fetch.fetch_repositories(self.username)

    def fetch_from_git_clone(self):
        """Fetch commits from git repositories."""
        commits_data, failed_repos = self.git_manager.fetch_repository_commits(
            self.username, self.data["repos"]
        )
        self.data["commits"] = commits_data
        self.data["errors"] = failed_repos

    def fetch_commit_messages(self):
        """Extract commit messages from fetched commits."""
        self.data["commits_msgs"] = self.git_manager.extract_commit_messages(
            self.data["commits"]
        )

    def fetch_recent_events(self):
        """Fetch list of last events for user profile."""
        self.data["recent_events"] = self.monitor.recent_events(self.username)

    def fetch_user_issues(self):
        """Fetch all issues created by the user."""
        try:
            self.data["issues"] = self.github_fetch.fetch_user_issues(self.username)
            logging.info(
                f"Fetched {len(self.data['issues'])} issues for {self.username}"
            )
        except Exception as e:
            logging.error(f"Error fetching issues for {self.username}: {e}")
            self.data["issues"] = []

    def fetch_user_comments(self):
        """Fetch all comments made by the user on issues."""
        try:
            self.data["comments"] = self.github_fetch.fetch_user_issue_comments(
                self.username
            )
            logging.info(
                f"Fetched {len(self.data['comments'])} issue comments for {self.username}"
            )
        except Exception as e:
            logging.error(f"Error fetching issue comments for {self.username}: {e}")
            self.data["comments"] = []

    def fetch_and_save_avatar(self):
        """Download and save user's avatar image using GithubFetchManager."""
        try:
            avatar_url = self.data["profile_data"].get("avatar_url")
            if avatar_url:
                avatar_filename = self.github_fetch.download_avatar(
                    avatar_url, self.data_manager.user_dir
                )
                if avatar_filename:
                    self.data["profile_data"]["local_avatar"] = avatar_filename

        except Exception as e:
            logging.error(f"Error handling avatar for {self.username}: {e}")

    def filter_created_at(self):
        """Compare repositories creation date with account's creation date ."""
        self.data["date_filter"] = self.data_filter.filter_by_creation_date(
            self.data["commits"], self.data["profile_data"]["created_at"]
        )

    def filter_commit_search(self):
        """Filter commits based on message similarity search."""
        try:
            self.data["commit_filter"] = self.data_filter.filter_commits_by_similarity(
                self.data["commits"]
            )
            self.data_manager.save_output(self.data)
        except Exception as e:
            logging.error(f"Error in filter_commit_search: {e}")

    def generate_report(self):
        """Generate a full account info dump to /out directory"""

        if not self.data:
            logging.info(f"Execute run_analysis() before generating the report.")
            return

        try:
            # Find mutual followers
            mutual_followers = set(
                f["login"] for f in self.data.get("followers", [])
            ) & set(f["login"] for f in self.data.get("following", []))

            # Find contributors to owner's repos
            contributors = []
            for repo in self.data["repos"]:
                if not repo["fork"]:
                    repo_name = repo["name"]
                    repo_contributors = self.github_fetch.fetch_repository_contributors(
                        self.username, repo_name
                    )
                    if repo_contributors:
                        contributors.append(
                            {
                                "repo": repo_name,
                                "contributors": [
                                    contributor["login"]
                                    for contributor in repo_contributors
                                ],
                            }
                        )

            # Classify repos as forked or original
            repo_list = [
                repo["name"] for repo in self.data["repos"] if not repo["fork"]
            ]
            forked_repo_list = [
                repo["name"] for repo in self.data["repos"] if repo["fork"]
            ]

            # Find unique emails in commit messages and connect with commits
            unique_emails = {}
            for repo_name, commits in self.data["commits"].items():
                for commit in commits:
                    author_email = commit["commit"]["author"]["email"]
                    author_name = commit["commit"]["author"]["name"]
                    committer_email = commit["commit"]["committer"]["email"]
                    committer_name = commit["commit"]["committer"]["name"]

                    if author_email not in unique_emails:
                        unique_emails[author_email] = author_name
                    if committer_email not in unique_emails:
                        unique_emails[committer_email] = committer_name

            unique_emails_list = [
                {"email": email, "name": name} for email, name in unique_emails.items()
            ]

            # Calculate the total count of original and forked repos
            original_repos_count = sum(
                1 for repo in self.data["repos"] if not repo["fork"]
            )
            forked_repos_count = sum(1 for repo in self.data["repos"] if repo["fork"])

            # Check if user has contributed to other repositories via PRs
            pull_requests_to_other_repos = {}
            search_results = self.github_fetch.search_pull_requests(self.username)

            if search_results:
                for item in search_results:
                    repo_name = item["repository_url"].split("/")[-1]
                    owner_name = item["repository_url"].split("/")[-2]
                    if owner_name != self.username:
                        pr_url = item["html_url"]
                        repo_key = f"{owner_name}/{repo_name}"
                        if repo_key not in pull_requests_to_other_repos:
                            pull_requests_to_other_repos[repo_key] = []
                        pull_requests_to_other_repos[repo_key].append(pr_url)

            # Check if user has made commits to other repositories
            commits_to_other_repos = {}
            search_commits_results = self.github_fetch.search_commits(self.username)

            if search_commits_results:
                for item in search_commits_results:
                    repo_name = item["repository"]["html_url"].split("/")[-1]
                    owner_name = item["repository"]["owner"]["login"]
                    if owner_name != self.username:
                        commit_sha = item["sha"]
                        repo_key = f"{owner_name}/{repo_name}"
                        if repo_key not in commits_to_other_repos:
                            commits_to_other_repos[repo_key] = []
                        commits_to_other_repos[repo_key].append(commit_sha)

            pull_requests_list = [
                {"repo": repo, "pull_requests": prs}
                for repo, prs in pull_requests_to_other_repos.items()
            ]
            commits_list = [
                {"repo": repo, "commits": commits}
                for repo, commits in commits_to_other_repos.items()
            ]

            # Clean followers & following lists in report
            followers_list = [f["login"] for f in self.data["followers"]]
            following_list = [f["login"] for f in self.data.get("following", [])]

            # Extract desired fields from profile_data
            profile_info = {
                key: self.data["profile_data"].get(key)
                for key in [
                    "login",
                    "id",
                    "node_id",
                    "avatar_url",
                    "html_url",
                    "type",
                    "site_admin",
                    "name",
                    "company",
                    "blog",
                    "location",
                    "email",
                    "hireable",
                    "bio",
                    "twitter_username",
                    "public_repos",
                    "public_gists",
                    "followers",
                    "following",
                    "created_at",
                    "updated_at",
                ]
            }

            cleaned_repos = self.data_manager.remove_repos_keys(
                self.data.get("repos", [])
            )

            report_data = {
                "profile_info": profile_info,
                "original_repos_count": original_repos_count,
                "forked_repos_count": forked_repos_count,
                "mutual_followers": list(mutual_followers),
                "following": following_list,
                "followers": followers_list,
                "repo_list": repo_list,
                "forked_repo_list": forked_repo_list,
                "unique_emails": unique_emails_list,
                "contributors": contributors,
                "pull_requests_to_other_repos": pull_requests_list,
                "commits_to_other_repos": commits_list,
                "repos": cleaned_repos,
                "commits": self.data.get("commits", {}),
                "errors": self.data.get("errors", []),
                "commit_filter": self.data.get("commit_filter", []),
                "recent_events": self.data.get("recent_events", []),
                "issues": self.data.get("issues", []),
                "comments": self.data.get("comments", []),
                "potential_copy": self.data.get("date_filter", []),
            }

            self.data_manager.save_output(report_data)

            logging.info(
                f"Report generated and saved to {self.data_manager.report_file}"
            )
        except Exception as e:
            logging.error(f"Error in generate_report: {e}")
