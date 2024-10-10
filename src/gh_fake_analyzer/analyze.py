import shutil
import requests
import json
import argparse
import time
import os
import git
from dotenv import load_dotenv
from dateutil import parser
import logging
import configparser

# Get the path to the configuration file analyzer is using
def get_config_path():
    # Default configuration file in the user's home directory
    user_config = os.path.expanduser("~/.gh_fake_analyzer_config.ini")
    # Optional local configuration file in the current working directory
    local_config = os.path.join(os.getcwd(), "config.ini")
    return local_config if os.path.exists(local_config) else user_config


# Get paths for configuration and log files
config_path = get_config_path()

# Load configuration
config = configparser.ConfigParser()
config.read(config_path)

# Set limits for the script
MAX_FOLLOWING = int(config["LIMITS"]["MAX_FOLLOWING"])
MAX_FOLLOWERS = int(config["LIMITS"]["MAX_FOLLOWERS"])
MAX_REPOSITORIES = int(config["LIMITS"]["MAX_REPOSITORIES"])
CLONE_DEPTH = int(config["LIMITS"]["CLONE_DEPTH"])

# Load environment variables from .env file
load_dotenv()

class APIUtils:
    GITHUB_API_URL = "https://api.github.com"
    BASE_GITHUB_URL = "https://github.com/"
    HEADERS = {"Accept": "application/vnd.github.v3+json"}
    RETRY_LIMIT = 10
    ITEMS_PER_PAGE = 100
    SLEEP_INTERVAL = 1

    @classmethod
    def set_token(cls, token):
        if token:
            cls.HEADERS["Authorization"] = f"token {token}"

    @classmethod
    def github_api_request(cls, url, params=None):
        retry_count = 0
        while retry_count < cls.RETRY_LIMIT:
            try:
                response = requests.get(url, headers=cls.HEADERS, params=params)
                print(f"Request URL: {response.url}")
                logging.info(f"Request URL: {response.url}")

                if response.status_code in [403, 429]:
                    cls._handle_rate_limit(response, retry_count)
                    retry_count += 1
                    continue
                elif response.status_code == 200:
                    time.sleep(cls.SLEEP_INTERVAL)
                    return response.json(), response.headers
                else:
                    logging.error(f"Request failed with status {response.status_code}.")
                    return None, None
            except requests.exceptions.RequestException as e:
                logging.error(f"An error occurred: {e}")
                return None, None

        return None, None

    @classmethod
    def _handle_rate_limit(cls, response, retry_count):
        if (
            "X-RateLimit-Remaining" in response.headers
            and response.headers["X-RateLimit-Remaining"] == "0"
        ):
            reset_time = int(response.headers["X-RateLimit-Reset"])
            sleep_time = max(0, reset_time - time.time())
            logging.warning(
                f"Primary rate limit exceeded. Sleeping for {sleep_time} seconds."
            )
            time.sleep(sleep_time + 1)
        elif "Retry-After" in response.headers:
            sleep_time = int(response.headers["Retry-After"])
            logging.warning(
                f"Secondary rate limit exceeded. Sleeping for {sleep_time} seconds."
            )
            time.sleep(sleep_time)
        else:
            sleep_time = int(pow(2, retry_count))
            logging.warning(
                f"Secondary rate limit exceeded. Retrying in {sleep_time} seconds."
            )
            time.sleep(sleep_time)

    @classmethod
    def fetch_all_pages(cls, url, params=None, limit=None):
        results = []
        while url and (limit is None or len(results) < limit):
            response, headers = cls.github_api_request(url, params)
            if response:
                new_items = (
                    response["items"]
                    if isinstance(response, dict) and "items" in response
                    else response
                )
                results.extend(
                    new_items[: limit - len(results)]
                    if limit is not None
                    else new_items
                )
                url = cls._get_next_url(headers)
                params = None
            else:
                break
        return results[:limit] if limit is not None else results

    @staticmethod
    def _get_next_url(headers):
        if "Link" in headers:
            links = requests.utils.parse_header_links(headers["Link"])
            return next((link["url"] for link in links if link["rel"] == "next"), None)
        return None


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


class DataManager:
    # Clutter to remove from profile data
    KEYS_TO_REMOVE = [
        "followers_url",
        "following_url",
        "gists_url",
        "starred_url",
        "subscriptions_url",
        "organizations_url",
        "repos_url",
        "events_url",
        "received_events_url",
        "forks_url",
        "keys_url",
        "collaborators_url",
        "teams_url",
        "hooks_url",
        "issue_events_url",
        "assignees_url",
        "branches_url",
        "tags_url",
        "blobs_url",
        "git_tags_url",
        "git_refs_url",
        "trees_url",
        "statuses_url",
        "languages_url",
        "stargazers_url",
        "contributors_url",
        "subscribers_url",
        "subscription_url",
        "commits_url",
        "git_commits_url",
        "comments_url",
        "issue_comment_url",
        "contents_url",
        "compare_url",
        "merges_url",
        "archive_url",
        "downloads_url",
        "issues_url",
        "pulls_url",
        "milestones_url",
        "notifications_url",
        "labels_url",
        "releases_url",
        "deployments_url",
        "git_url",
        "ssh_url",
        "clone_url",
        "svn_url",
    ]

    def __init__(self, username, out_path=None):
        self.username = username
        if out_path:
            self.user_dir = os.path.join(out_path, username)
        else:
            self.user_dir = os.path.join(os.getcwd(), "out", username)
        if not os.path.exists(self.user_dir):
            os.makedirs(self.user_dir)

        self.report_file = os.path.join(self.user_dir, "report.json")

    def save_output(self, data):
        try:
            filtered_data = self.remove_unwanted_keys(data)
            self.save_to_json(filtered_data, self.report_file)
            logging.info(f"Data saved to {self.report_file}")
        except Exception as e:
            logging.error(f"Error in save_output: {e}")

    def save_to_json(self, data, filename):
        try:
            with open(filename, "w", encoding="utf-8") as json_file:
                json.dump(data, json_file, indent=4, ensure_ascii=False)
            logging.info(f"Successfully saved data to {filename}")
        except Exception as e:
            logging.error(f"Error in save_to_json for {filename}: {e}")
            raise

    def load_existing(self):
        try:
            if os.path.exists(self.report_file):
                with open(self.report_file, "r", encoding="utf-8") as json_file:
                    return json.load(json_file)
            else:
                logging.info("No existing data file found")
                return None
        except Exception as e:
            logging.error(f"Error in load_existing: {e}")
            return None

    def remove_unwanted_keys(self, data):
        if isinstance(data, dict):
            return {
                key: self.remove_unwanted_keys(value)
                for key, value in data.items()
                if key not in self.KEYS_TO_REMOVE
            }
        elif isinstance(data, list):
            return [self.remove_unwanted_keys(item) for item in data]
        else:
            return data

    def remove_repos_keys(self, repos):
        cleaned_repos = []
        for repo in repos:
            cleaned_repo = {
                k: v for k, v in repo.items() if k not in self.KEYS_TO_REMOVE
            }

            if "owner" in repo:
                cleaned_repo["owner"] = {"login": repo["owner"].get("login")}
            if "license" in repo and repo["license"]:
                cleaned_repo["license"] = {
                    "key": repo["license"].get("key"),
                    "name": repo["license"].get("name"),
                    "spdx_id": repo["license"].get("spdx_id"),
                }
            cleaned_repos.append(cleaned_repo)
        return cleaned_repos


class GitHubProfileAnalyzer:
    def __init__(self, username, out_path=None):
        self.username = username
        self.data_manager = DataManager(username, out_path)
        self.git_manager = GitManager(username, self.data_manager.user_dir)
        self.api_utils = APIUtils()
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
            self.filter_created_at()
            logging.info(f"Analysis completed for {self.username}")
        except Exception as e:
            logging.error(f"Error in run_analysis for {self.username}: {e}")

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

            # Convert dictionaries to lists of objects
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


def read_targets(file_path):
    """Reads a list of GitHub usernames from a file."""
    try:
        with open(file_path, "r") as file:
            targets = file.read().splitlines()
        if targets:
            logging.info(f"Targets read from {file_path}")
        return targets
    except Exception as e:
        logging.error(f"Error reading targets file {file_path}: {e}")
        return []


def process_target(username, commit_search=False, only_profile=False, out_path=None):
    try:
        analyzer = GitHubProfileAnalyzer(username, out_path=out_path)

        if only_profile:
            logging.info(f"Only fetching profile data for {username}...")
            analyzer.fetch_profile_data()
            analyzer.data_manager.save_output(analyzer.data)
            return

        logging.info(f"Starting full analysis for {username}...")
        analyzer.run_analysis()

        if commit_search:
            logging.info(f"Searching for copied commits in {username}'s repos...")
            analyzer.filter_commit_search()

        # NOTE: CLI will always re-download data
        logging.info(f"Generating report for {username}...")
        analyzer.generate_report()

        logging.info(f"Processing completed for {username}")
    except Exception as e:
        logging.error(f"Error processing target {username}: {e}")
        print(f"Error processing target {username}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Analyze GitHub profiles.")
    parser.add_argument(
        "username",
        type=str,
        nargs="?",
        help="GitHub username to analyze (if omitted, reads from targets file)",
    )
    parser.add_argument(
        "--only_profile",
        action="store_true",
        help="Only fetch profile data (no commits, followers, etc.)",
    )
    parser.add_argument(
        "--targets",
        nargs="?",
        const="targets",
        help="File containing a list of GitHub usernames to analyze (defaults to 'targets')",
    )
    parser.add_argument(
        "--commit_search",
        action="store_true",
        help="Query GitHub API search for similar commits",
    )

    parser.add_argument(
        "--token", help="Optional GitHub API token overriding set env variable"
    )

    parser.add_argument(
        "--out_path",
        type=str,
        nargs="?",
        help="Output directory for analysis results",
    )

    args = parser.parse_args()
    start_time = time.time()

    if args.token:
        APIUtils.set_token(args.token)
    elif os.getenv("GH_TOKEN"):
        APIUtils.set_token(os.getenv("GH_TOKEN"))
    else:
        logging.warning("No GitHub token provided. Rate limits may apply.")
        print("No GitHub token provided. Rate limits may apply.")
        
    if args.only_profile:
        logging.info(f"Only fetching profile data for {args.username}...")
        process_target(args.username, only_profile=True, out_path=args.out_path)
        return

    if args.username:
        logging.info(f"Processing single target: {args.username}")
        process_target(args.username, args.commit_search, out_path=args.out_path)

    if args.targets:
        targets_file = args.targets
        logging.info(f"Processing targets from file: {targets_file}")
        print(f"Processing targets from file: {targets_file}")

        targets = read_targets(targets_file)
        if not targets:
            logging.error(f"No targets found in {targets_file}. Exiting.")
            print(
                f"No targets found in {targets_file}. Please provide a valid targets file or specify a username."
            )
            return

        for target in targets:
            logging.info(f"Processing target: {target}")
            process_target(target, args.commit_search, out_path=args.out_path)
    
    if not args.username and not args.targets:
        logging.error("No targets specified. Exiting.")
        print("No targets specified. Please provide a valid username or targets file.")
        print("Print help with -h or --help.")

    end_time = time.time()
    print(f"Processing completed in {end_time - start_time:.2f} seconds.")
    logging.info(f"Processing completed in {end_time - start_time:.2f} seconds.")

def setup_logging():
    log_path = os.path.join(os.getcwd(), "script.log")
    logging.basicConfig(
        filename=log_path,
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

def run_analyzer():
    setup_logging()
    main()

if __name__ == "__main__":
    main()
