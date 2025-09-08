import logging
from ..utils.api import APIUtils
from ..utils.data import DataManager
from ..utils.github import GitCloneManager
from .fetch import GithubFetchManager
from .filter import GitHubDataFilter
from .monitor import GitHubMonitor
from .categorize_emails import EmailCategorizer
from typing import Dict
import re


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
            self.fetch_contributors()
            self.fetch_recent_events()
            self.fetch_received_events()
            self.fetch_user_issues()
            self.fetch_user_comments()
            self.fetch_user_organizations()
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
        try:
            events = self.monitor.recent_events(self.username)
            self.data["recent_events"] = events
            logging.info(f"Fetched {len(events)} recent events for {self.username}")
        except Exception as e:
            logging.error(f"Error fetching recent events for {self.username}: {e}")
            self.data["recent_events"] = []

    def fetch_received_events(self):
        """Fetch list of last events for a specific user."""
        try:
            events = self.monitor.recent_events_by_user(self.username)
            self.data["received_events"] = events
            logging.info(f"Fetched {len(events)} received events for {self.username}")
        except Exception as e:
            logging.error(f"Error fetching received events for {self.username}: {e}")
            self.data["received_events"] = []

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

    def filter_commit_search(self, repo_name=None):
        """
        Filter commits based on message similarity search.
        Extends existing commit_filter data with new results.

        Args:
            repo_name (str, optional): If provided, only search commits from this repository
        """
        try:

            if "commit_filter" not in self.data:
                self.data["commit_filter"] = []

            new_results = self.data_filter.filter_commits_by_similarity(
                self.data["commits"], repo_name=repo_name
            )

            if repo_name:
                self.data["commit_filter"] = [
                    result
                    for result in self.data["commit_filter"]
                    if result["target_repo"] != repo_name
                ]

            self.data["commit_filter"].extend(new_results)
            self.data_manager.save_output(self.data)

        except Exception as e:
            logging.error(f"Error in filter_commit_search: {e}")

    def _generate_unique_emails(self) -> list:
        """Generates the unique_emails data structure."""
        # First check if we have commits data
        if "commits" not in self.data:
            logging.error("No commits data found in self.data")
            return [{"owner": [], "contributors": [], "other": []}]

        commits_data = self.data["commits"]
        
        # Ensure commits_data is a dictionary
        if not isinstance(commits_data, dict):
            logging.error(f"Expected commits_data to be a dict, got {type(commits_data)}")
            return [{"owner": [], "contributors": [], "other": []}]

        # Get contributors data
        contributors_data = self.data.get("contributors", {})
        
        # Initialize email categorizer with the contributors data
        email_categorizer = EmailCategorizer(
            username=self.username, 
            contributors_data=contributors_data
        )
        
        categorized_emails = email_categorizer.categorize_emails(
            commits_data=commits_data
        )
        
        return [  # Return as a list to maintain consistency
            {
                "owner": categorized_emails["owner_emails"],
                "contributors": categorized_emails["contributors_emails"],
                "other": categorized_emails["other_emails"],
            }
        ]


    def detect_identity_rotation(self) -> Dict:
        """Detects potential identity rotation based on email/name variations."""
        try:
            self.data["unique_emails"] = self._generate_unique_emails()
            
            # Initialize result structure
            rotation_flags = {
                "multiple_names_per_email": {},  # email -> {names: [], count: int}
                "multiple_emails_per_name": {},  # name -> {emails: [], count: int}
                "merge_messages": {},  # repo_name -> [merge_messages] (all merge messages for a repo)
            }
            
            # Process owner emails to find variations
            owner_emails = self.data["unique_emails"][0]["owner"]
            
            # Build email -> names and name -> emails mappings
            email_to_names = {}
            name_to_emails = {}
            all_commit_names = set()  # Track all names used in commits
            
            for entry in owner_emails:
                email = entry["email"]
                name = entry["name"]
                
                if email not in email_to_names:
                    email_to_names[email] = set()
                email_to_names[email].add(name)
                
                if name not in name_to_emails:
                    name_to_emails[name] = set()
                name_to_emails[name].add(email)
                
                # Add to all names if it looks like a username
                if ' ' not in name and name.lower() != self.username.lower():
                    all_commit_names.add(name)
            
            # Process emails with multiple names
            for email, names in email_to_names.items():
                if len(names) > 1:  # Only include if email has multiple names
                    rotation_flags["multiple_names_per_email"][email] = {
                        "names": sorted(list(names)),  # Sort for consistent output
                        "count": len(names)
                    }
            
            # Process names with multiple emails
            for name, emails in name_to_emails.items():
                if len(emails) > 1:  # Only include if name has multiple emails
                    rotation_flags["multiple_emails_per_name"][name] = {
                        "emails": sorted(list(emails)),  # Sort for consistent output
                        "count": len(emails)
                    }
                                            
            return rotation_flags

        except Exception as e:
            logging.error(f"Error detecting identity rotation for {self.username}: {e}")
            return {}


    def detect_dprk_naming(self) -> Dict:
        """Detects if usernames or email names match the DPRK-style pattern USERNAME[0-9][0-9][0-9][0-9]"""
        try:
            dprk_pattern = re.compile(r'^[a-zA-Z]+[0-9]{4}$')
            dprk_flags = {
                "usernames": [],  # List of usernames matching the pattern
                "email_names": [],  # List of email names (without domain) matching the pattern
                "contributor_names": []  # List of contributor names matching the pattern
            }
            
            # Check the main username
            if dprk_pattern.match(self.username):
                dprk_flags["usernames"].append(self.username)
            
            # Check owner emails and names from unique_emails
            if "unique_emails" in self.data and self.data["unique_emails"]:
                for entry in self.data["unique_emails"][0]["owner"]:
                    # Check the name
                    if dprk_pattern.match(entry["name"]):
                        dprk_flags["usernames"].append(entry["name"])
                    
                    # Check the email name (part before @)
                    email_name = entry["email"].split('@')[0]
                    if dprk_pattern.match(email_name):
                        dprk_flags["email_names"].append(email_name)
            
            # Check contributor names from contributors data
            if "contributors" in self.data:
                for contributor_data in self.data["contributors"]:
                    if "contributors" in contributor_data:
                        for contributor_name in contributor_data["contributors"]:
                            if dprk_pattern.match(contributor_name):
                                dprk_flags["contributor_names"].append(contributor_name)
            
            # Clean up empty categories
            if not dprk_flags["usernames"]:
                del dprk_flags["usernames"]
            if not dprk_flags["email_names"]:
                del dprk_flags["email_names"]
            if not dprk_flags["contributor_names"]:
                del dprk_flags["contributor_names"]
            
            return dprk_flags if dprk_flags else {}

        except Exception as e:
            logging.error(f"Error detecting DPRK naming patterns for {self.username}: {e}")
            return {}

    def fetch_user_organizations(self):
        """Fetch all organizations that the user is a member of."""
        try:
            orgs = self.github_fetch.fetch_user_organizations(self.username)
            self.data["organizations_member"] = [org["login"] for org in orgs]
            logging.info(f"Fetched {len(self.data['organizations_member'])} organizations for {self.username}")
        except Exception as e:
            logging.error(f"Error fetching organizations for {self.username}: {e}")
            self.data["organizations_member"] = []

    def fetch_contributors(self) -> None:
        """Fetch contributors for all non-forked repositories and store in self.data."""
        try:
            contributors = {}
            for repo in self.data["repos"]:
                if not repo["fork"]:
                    repo_name = repo["name"]
                    repo_contributors = self.github_fetch.fetch_repository_contributors(
                        self.username, repo_name
                    )
                    if repo_contributors:
                        contributors[repo_name] = [
                            contributor["login"]
                            for contributor in repo_contributors
                        ]
            self.data["contributors"] = contributors
        except Exception as e:
            logging.error(f"Error in contributors fetch: {e}")
            self.data["contributors"] = {}

    def generate_report(self):
        """Generate a full account info dump to /out directory"""

        if not self.data:
            logging.info(f"Execute run_analysis() before generating the report.")
            return

        try:
            # Find mutual followers
            try:
                mutual_followers = set(
                    f["login"] for f in self.data.get("followers", [])
                ) & set(f["login"] for f in self.data.get("following", []))
            except Exception as e:
                logging.error(f"Error in mutual followers calculation: {e}")
                raise

            # Classify repos as forked or original
            try:
                repo_list = [
                    repo["name"] for repo in self.data["repos"] if not repo["fork"]
                ]
                forked_repo_list = [
                    repo["name"] for repo in self.data["repos"] if repo["fork"]
                ]
            except Exception as e:
                logging.error(f"Error in repo classification: {e}")
                raise

            try:
                unique_emails_list = self._generate_unique_emails()
            except Exception as e:
                logging.error(f"Error in unique emails generation: {e}")
                raise

            # Calculate the total count of original and forked repos
            try:
                original_repos_count = sum(
                    1 for repo in self.data["repos"] if not repo["fork"]
                )
                forked_repos_count = sum(1 for repo in self.data["repos"] if repo["fork"])
            except Exception as e:
                logging.error(f"Error in repo counts calculation: {e}")
                raise

            # Find contributions to other repositories from commits data
            try:
                pull_requests_to_other_repos = {}
                commits_to_other_repos = {}

                # Process commits data to find external contributions
                # Get all PRs first - this is still necessary
                pull_requests_to_other_repos = {}
                search_results = self.github_fetch.search_pull_requests(self.username)

                if search_results:
                    for item in search_results:
                        repo_name = item["repository_url"].split("/")[-1]
                        owner_name = item["repository_url"].split("/")[-2]
                        if owner_name != self.username:
                            repo_key = f"{owner_name}/{repo_name}"
                            if repo_key not in pull_requests_to_other_repos:
                                pull_requests_to_other_repos[repo_key] = []
                            if item["number"] not in pull_requests_to_other_repos[repo_key]:
                                pull_requests_to_other_repos[repo_key].append(item["number"])

                # Get commits from both the commits data and additional search
                commits_to_other_repos = {}
                for repo_name, commits in self.data.get("commits", {}).items():
                    for commit in commits:
                        repo_owner = commit.get("repository", {}).get("owner", {}).get("login")
                        if repo_owner and repo_owner.lower() != self.username.lower():
                            repo_key = f"{repo_owner}/{repo_name}"
                            if repo_key not in commits_to_other_repos:
                                commits_to_other_repos[repo_key] = []
                            commits_to_other_repos[repo_key].append(commit["sha"])
            except Exception as e:
                logging.error(f"Error in external contributions processing: {e}")
                raise

            # Clean followers & following lists in report
            try:
                followers_list = [f["login"] for f in self.data["followers"]]
                following_list = [f["login"] for f in self.data.get("following", [])]
            except Exception as e:
                logging.error(f"Error in lists cleanup: {e}")
                raise

            # Extract desired fields from profile_data
            try:
                profile_info = {
                    key: self.data["profile_data"].get(key)
                    for key in [
                        "login", "id", "node_id", "avatar_url", "html_url", "type",
                        "site_admin", "name", "company", "blog", "location", "email",
                        "hireable", "bio", "twitter_username", "public_repos",
                        "public_gists", "followers", "following", "created_at",
                        "updated_at",
                    ]
                }
            except Exception as e:
                logging.error(f"Error in profile info extraction: {e}")
                raise

            try:
                cleaned_repos = self.data_manager.remove_repos_keys(
                    self.data.get("repos", [])
                )
            except Exception as e:
                logging.error(f"Error in repos cleanup: {e}")
                raise

            try:
                prs_to_organizations = list(
                    set([pr.split("/")[0] for pr in pull_requests_to_other_repos.keys()])
                )
                issues_to_organizations = list(
                    set([issue["repo"].split("/")[0] for issue in self.data.get("issues", [])])
                )
            except Exception as e:
                logging.error(f"Error in organizations processing: {e}")
                issues_to_organizations = []
                prs_to_organizations = []

            try:
                report_data = {
                    "profile_info": profile_info,
                    "original_repos_count": original_repos_count,
                    "forked_repos_count": forked_repos_count,
                    "unique_emails": unique_emails_list,
                    "dprk_naming": self.detect_dprk_naming(),
                    "identity_rotation": self.detect_identity_rotation(),
                    "mutual_followers": list(mutual_followers),
                    "potential_copy": self.data.get("date_filter", []),
                    "contributors": self.data.get("contributors", {}),
                    "following": following_list,
                    "followers": followers_list,
                    "repo_list": repo_list,
                    "forked_repo_list": forked_repo_list,
                    "pull_requests_to_other_repos": pull_requests_to_other_repos,
                    "prs_to_organizations": prs_to_organizations,
                    "commits_to_other_repos": commits_to_other_repos,
                    "repos": cleaned_repos,
                    "commits": self.data.get("commits", {}),
                    "errors": self.data.get("errors", []),
                    "commit_filter": self.data.get("commit_filter", []),
                    "recent_events": self.data.get("recent_events", []),
                    "received_events": self.data.get("received_events", []),
                    "issues": self.data.get("issues", []),
                    "issues_to_organizations": issues_to_organizations,
                    "comments": self.data.get("comments", []),
                    "organizations_member": self.data.get("organizations_member", []),
                }

                self.data_manager.save_output(report_data)

                logging.info(
                    f"Report generated and saved to {self.data_manager.report_file}"
                )
                
                return report_data
            
            except Exception as e:
                logging.error(f"Error in report assembly and save: {e}")
                raise

        except Exception as e:
            logging.error(f"Error in generate_report: {e}")
            raise
