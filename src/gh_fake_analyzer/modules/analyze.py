import requests
import logging
from dateutil import parser
from ..utils.api import APIUtils
from ..utils.data import DataManager
from ..utils.github import GitManager
from ..utils.config import MAX_FOLLOWING, MAX_FOLLOWERS, MAX_REPOSITORIES
from .monitor import GitHubMonitor 

class GitHubProfileAnalyzer:
    def __init__(self, username, out_path=None):
        self.username = username
        self.data_manager = DataManager(username, out_path)
        self.git_manager = GitManager(username, self.data_manager.user_dir)
        self.api_utils = APIUtils()
        self.monitor = GitHubMonitor(APIUtils)
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
        url = f"{self.api_utils.GITHUB_API_URL}/users/{self.username}"
        self.data["profile_data"], _ = self.api_utils.github_api_request(url)

    def fetch_following(self):
        url = f"{self.api_utils.GITHUB_API_URL}/users/{self.username}/following"
        self.data["following"] = self.api_utils.fetch_all_pages(
            url, {"per_page": self.api_utils.ITEMS_PER_PAGE}, limit=MAX_FOLLOWING
        )

    def fetch_followers(self):
        url = f"{self.api_utils.GITHUB_API_URL}/users/{self.username}/followers"
        self.data["followers"] = self.api_utils.fetch_all_pages(
            url, {"per_page": self.api_utils.ITEMS_PER_PAGE}, limit=MAX_FOLLOWERS
        )

    def fetch_profile_repos(self):
        url = f"{self.api_utils.GITHUB_API_URL}/users/{self.username}/repos"
        self.data["repos"] = self.api_utils.fetch_all_pages(
            url, {"per_page": self.api_utils.ITEMS_PER_PAGE}, limit=MAX_REPOSITORIES
        )

    def fetch_from_git_clone(self):
        self.data["commits"] = {}
        failed_repos = []
        for repo in self.data["repos"]:
            if not repo["fork"]:
                repo_name, commits = self.git_manager.clone_and_fetch_commits(repo)
                if isinstance(commits, dict) and "error" in commits:
                    failed_repos.append(
                        {
                            "repo_name": repo_name,
                            "clone_url": repo["clone_url"],
                            "reason": commits["error"],
                        }
                    )
                else:
                    self.data["commits"][repo_name] = commits
        self.data["errors"] = failed_repos

    def fetch_commit_messages(self):
        self.data["commits_msgs"] = {
            repo: [commit["commit"]["message"] for commit in commits]
            for repo, commits in self.data["commits"].items()
        }

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
                    url = f"{self.api_utils.GITHUB_API_URL}/repos/{self.username}/{repo_name}/contributors"
                    repo_contributors = self.api_utils.fetch_all_pages(url)
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
            search_url = f"{self.api_utils.GITHUB_API_URL}/search/issues"
            search_params = {
                "q": f"type:pr author:{self.username}",
                "per_page": self.api_utils.ITEMS_PER_PAGE,
            }
            pull_requests_to_other_repos = {}
            search_results = self.api_utils.fetch_all_pages(search_url, search_params)

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
            search_commits_url = f"{self.api_utils.GITHUB_API_URL}/search/commits"
            search_commits_params = {
                "q": f"author:{self.username}",
                "per_page": self.api_utils.ITEMS_PER_PAGE,
            }
            commits_to_other_repos = {}
            search_commits_results = self.api_utils.fetch_all_pages(
                search_commits_url, search_commits_params
            )

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

            # Construct GitHub HTML links for followers and following (without prefix)
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
                "recent_events": self.data.get("recent_events", [])
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
                        if 20 < commit_len < 150:
                            message = commit_message.replace("\n", " ").replace(
                                "\r", " "
                            )

                            search_url = (
                                f"{self.api_utils.GITHUB_API_URL}/search/commits"
                            )
                            search_params = {
                                "q": message,
                                "per_page": self.api_utils.ITEMS_PER_PAGE,
                            }

                            try:
                                search_results, _ = self.api_utils.github_api_request(
                                    search_url, params=search_params
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
