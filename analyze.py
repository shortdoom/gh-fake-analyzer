import shutil
import requests
import json
import argparse
from collections import defaultdict
import time
import os
import git
from dotenv import load_dotenv
from dateutil import parser
import logging

# Configure logging
logging.basicConfig(
    filename="script.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Load environment variables from .env file
load_dotenv()
GH_TOKEN = os.getenv("GH_TOKEN")


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
    def fetch_all_pages(cls, url, params=None):
        results = []
        while url:
            response, headers = cls.github_api_request(url, params)
            if response:
                results.extend(
                    response["items"]
                    if isinstance(response, dict) and "items" in response
                    else response
                )
                url = cls._get_next_url(headers)
                params = None
            else:
                break
        return results

    @staticmethod
    def _get_next_url(headers):
        if "Link" in headers:
            links = requests.utils.parse_header_links(headers["Link"])
            return next((link["url"] for link in links if link["rel"] == "next"), None)
        return None


class DataManager:
    def __init__(self, username, out_path=None):
        self.username = username

        if out_path:
            self.user_dir = os.path.join(out_path, username)
            self.data_file = os.path.join(self.user_dir, f"{username}.json")
            
            if not os.path.exists(self.user_dir):
                os.makedirs(self.user_dir)
        else:
            self.user_dir = os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "out", username
            )
            self.data_file = os.path.join(self.user_dir, f"{username}.json")

            if not os.path.exists(self.user_dir):
                os.makedirs(self.user_dir)

    def save_output(self, data):
        self.save_to_json(data, self.data_file)

    def load_existing(self):
        try:
            with open(self.data_file, "r") as json_file:
                return json.load(json_file)
        except Exception as e:
            logging.error(f"Error in load_existing: {e}")
            return None

    def save_to_json(self, data, filename):
        try:
            with open(filename, "w") as json_file:
                json.dump(data, json_file, indent=4)
        except Exception as e:
            logging.error(f"Error in save_to_json: {e}")

    def save_failed_repos(self, failed_repos):
        failed_repos_file = os.path.join(self.user_dir, "failed_repos.json")
        self.save_to_json(failed_repos, failed_repos_file)


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
            git.Repo.clone_from(clone_url, repo_dir, bare=True, depth=100)
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
            "parents": [p.hexsha for p in commit.parents],
            "url": f"https://github.com/{self.username}/{os.path.basename(commit.repo.working_dir).replace(f'{self.username}_', '').replace('.git', '')}/commit/{commit.hexsha}",
        }


class GitHubProfileAnalyzer:
    def __init__(self, username, out_path=None):
        self.username = username
        self.data_manager = DataManager(username, out_path)
        self.git_manager = GitManager(username, self.data_manager.user_dir)
        self.api_utils = APIUtils()

        # NOTE: Read-in previous analysis results, useful if you use Class directly
        self.data = self.data_manager.load_existing() or {}

    def run_analysis(self):
        try:
            self.fetch_profile_data()
            self.fetch_following()
            self.fetch_followers()
            self.fetch_profile_repos()
            self.fetch_from_git_clone()
            self.fetch_commit_messages()
            self.filter_created_at()
            self.data_manager.save_output(self.data)
        except Exception as e:
            logging.error(f"Error in run_analysis: {e}")

    def fetch_profile_data(self):
        url = f"{self.api_utils.GITHUB_API_URL}/users/{self.username}"
        self.data["profile_data"], _ = self.api_utils.github_api_request(url)

    def fetch_following(self):
        url = f"{self.api_utils.GITHUB_API_URL}/users/{self.username}/following"
        self.data["following"] = self.api_utils.fetch_all_pages(
            url, {"per_page": self.api_utils.ITEMS_PER_PAGE}
        )

    def fetch_followers(self):
        url = f"{self.api_utils.GITHUB_API_URL}/users/{self.username}/followers"
        self.data["followers"] = self.api_utils.fetch_all_pages(
            url, {"per_page": self.api_utils.ITEMS_PER_PAGE}
        )

    def fetch_profile_repos(self):
        url = f"{self.api_utils.GITHUB_API_URL}/users/{self.username}/repos"
        self.data["repos"] = self.api_utils.fetch_all_pages(
            url, {"per_page": self.api_utils.ITEMS_PER_PAGE}
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
        self.data_manager.save_failed_repos(failed_repos)

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
            contributors = defaultdict(set)
            for repo in self.data["repos"]:
                if not repo["fork"]:
                    repo_name = repo["name"]
                    url = f"{self.api_utils.GITHUB_API_URL}/repos/{self.username}/{repo_name}/contributors"
                    repo_contributors = self.api_utils.fetch_all_pages(url)
                    if repo_contributors:
                        for contributor in repo_contributors:
                            contributors[repo_name].add(contributor["login"])

            # Classify repos as forked or original
            repo_list = [
                repo["name"] for repo in self.data["repos"] if not repo["fork"]
            ]
            forked_repo_list = [
                repo["name"] for repo in self.data["repos"] if repo["fork"]
            ]

            # Find unique emails in commit messages
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
                        key = f"{owner_name}/{repo_name}"
                        if key not in pull_requests_to_other_repos:
                            pull_requests_to_other_repos[key] = []
                        pull_requests_to_other_repos[key].append(pr_url)

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
                        commit_url = item["html_url"]
                        key = f"{owner_name}/{repo_name}"
                        if key not in commits_to_other_repos:
                            commits_to_other_repos[key] = []
                        commits_to_other_repos[key].append(commit_url)

            # Construct full GitHub HTML links for followers and following
            followers_list = [
                f"{self.api_utils.BASE_GITHUB_URL}{f['login']}"
                for f in self.data["followers"]
            ]

            following_list = [
                f"{self.api_utils.BASE_GITHUB_URL}{f['login']}"
                for f in self.data.get("following", [])
            ]

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

            report_data = {
                "profile_info": profile_info,
                "original_repos_count": original_repos_count,
                "forked_repos_count": forked_repos_count,
                "unique_emails": unique_emails,
                "mutual_followers": list(mutual_followers),
                "following": following_list,
                "followers": followers_list,
                "repo_list": repo_list,
                "forked_repo_list": forked_repo_list,
                "contributors": {
                    repo: list(users) for repo, users in contributors.items()
                },
                "pull_requests_to_other_repos": pull_requests_to_other_repos,
                "commits_to_other_repos": commits_to_other_repos,
            }

            if self.data.get("date_filter"):
                report_data["potential_copy"] = self.data["date_filter"]

            report_file = os.path.join(self.data_manager.user_dir, "report.json")
            self.data_manager.save_to_json(report_data, report_file)

            logging.info(f"Report generated and saved to {report_file}")
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
                                        item["repository"]["html_url"]
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
    """Process an individual GitHub profile."""
    try:
        analyzer = GitHubProfileAnalyzer(username, out_path=out_path)

        if only_profile:
            logging.info(f"Only fetching profile data for {username}...")
            analyzer.fetch_profile_data()
            analyzer.data_manager.save_output(analyzer.data)
            return

        if not analyzer.data:
            logging.info(f"Analyzing profile data for {username}...")
            analyzer.run_analysis()
        else:
            logging.info(f"Profile data for {username} already exists.")

        if commit_search:
            logging.info(f"Searching for copied commits in {username}'s repos...")
            analyzer.filter_commit_search()

        logging.info(f"Generating report for {username}...")
        analyzer.generate_report()
    except Exception as e:
        logging.error(f"Error processing target {username}: {e}")


def main():
    APIUtils.set_token(GH_TOKEN)
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
        "--out_path",
        type=str,
        nargs="?",
        help="Output directory for analysis results",
    )

    args = parser.parse_args()
    start_time = time.time()

    if args.only_profile:
        logging.info(f"Only fetching profile data for {args.username}...")
        process_target(args.username, only_profile=True, out_path=args.out_path)
        return

    if args.username:
        # Process single target
        logging.info(f"Processing single target: {args.username}")
        process_target(args.username, args.commit_search, out_path=args.out_path)
    else:
        # Determine targets file
        targets_file = args.targets if args.targets is not None else "targets"
        logging.info(f"Processing targets from file: {targets_file}")
        print(f"Processing targets from file: {targets_file}")

        targets = read_targets(targets_file)
        if not targets:
            logging.error(f"No targets found in {targets_file}. Exiting.")
            print(
                f"No targets found in {targets_file}. Please provide a valid targets file or specify a username."
            )
            return

        # Process each target
        for target in targets:
            logging.info(f"Processing target: {target}")
            process_target(target, args.commit_search, out_path=args.out_path)

    end_time = time.time()
    print(f"Processing completed in {end_time - start_time:.2f} seconds.")
    logging.info(f"Processing completed in {end_time - start_time:.2f} seconds.")


if __name__ == "__main__":
    main()
