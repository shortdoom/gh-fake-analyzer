import requests
import logging
from dateutil import parser
from ..utils.api import APIUtils
from ..utils.data import DataManager
from ..utils.github import GitCloneManager
from .monitor import GitHubMonitor
from .fetch import FetchFromGithub


class GitHubProfileAnalyzer:
    def __init__(self, username, out_path=None):
        self.username = username
        self.data_manager = DataManager(username, out_path)
        self.git_manager = GitCloneManager(self.data_manager.user_dir)
        self.api_utils = APIUtils()
        self.monitor = GitHubMonitor(self.api_utils)
        self.github_fetch = FetchFromGithub(self.api_utils)
        self.data = self.data_manager.load_existing() or {}
        logging.info(f"GitHubProfileAnalyzer initialized for {username}")
        logging.info(
            f"{'Found' if self.data else 'No'} data in {self.data_manager.report_file}"
        )

    def run_analysis(self):
        try:
            self.fetch_profile_data()
            self.fetch_following()
            self.fetch_followers()
            self.fetch_profile_repos()
            self.fetch_from_git_clone()
            self.fetch_commit_messages()
            self.fetch_recent_events()
            self.filter_created_at()
            logging.info(f"Analysis completed for {self.username}")
        except Exception as e:
            logging.error(f"Error in run_analysis for {self.username}: {e}")

    def fetch_recent_events(self):
        self.data["recent_events"] = self.monitor.recent_events(self.username)

    def fetch_profile_data(self):
        self.data["profile_data"] = self.github_fetch.fetch_profile_data(self.username)

    def fetch_following(self):
        self.data["following"] = self.github_fetch.fetch_following(
            self.username,
        )

    def fetch_followers(self):
        self.data["followers"] = self.github_fetch.fetch_followers(
            self.username,
        )

    def fetch_profile_repos(self):
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

    def filter_created_at(self):
        account_created_at = parser.parse(self.data["profile_data"]["created_at"])
        self.data["date_filter"] = []
        for repo_name, commits in self.data["commits"].items():
            if commits:
                first_commit_date = parser.parse(
                    commits[-1]["commit"]["author"]["date"]
                )
                if first_commit_date < account_created_at:
                    self.data["date_filter"].append(
                        {
                            "repo": repo_name,
                            "reason": "account creation date later than the first commit to the repository",
                            "commit_date": first_commit_date.isoformat(),
                        }
                    )

    def generate_report(self):
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
            }

            if self.data.get("date_filter"):
                report_data["potential_copy"] = self.data["date_filter"]

            self.data_manager.save_output(report_data)

            logging.info(
                f"Report generated and saved to {self.data_manager.report_file}"
            )
        except Exception as e:
            logging.error(f"Error in generate_report: {e}")

    def filter_commit_search(self):
        try:
            self.data["commit_filter"] = []
            for repo_name, commits in self.data["commits"].items():
                if commits:
                    for commit in commits:
                        commit_message = commit["commit"]["message"]
                        commit_len = len(commit_message)
                        # TODO: Better heuristics here than len()
                        if 20 < commit_len < 150:
                            message = commit_message.replace("\n", " ").replace(
                                "\r", " "
                            )
                            try:
                                search_results, _ = self.github_fetch.search_commits(
                                    None, message
                                )

                                if (
                                    search_results
                                    and search_results.get("total_count", 0) > 0
                                ):
                                    matching_repos = [
                                        item["repository"]["html_url"].replace(
                                            "https://github.com/", ""
                                        )
                                        for item in search_results["items"]
                                    ]
                                    self.data["commit_filter"].append(
                                        {
                                            "target_repo": repo_name,
                                            "target_commit": commit_message,
                                            "search_results": search_results[
                                                "total_count"
                                            ],
                                            "matching_repos": matching_repos,
                                        }
                                    )
                            except requests.exceptions.HTTPError as e:
                                logging.error(f"Error fetching search results: {e}")
                else:
                    self.data["commit_filter"].append(
                        {
                            "target_repo": repo_name,
                            "target_commit": "No commits found",
                            "search_results": 0,
                            "matching_repos": [],
                        }
                    )

            self.data_manager.save_output(self.data)

        except Exception as e:
            logging.error(f"Error in filter_commit_search: {e}")
