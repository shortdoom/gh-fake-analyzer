import requests
from datetime import datetime
import json
import argparse
from collections import defaultdict
import time
import os
import git
from git import Git
from dotenv import load_dotenv
from dateutil import parser


# Load environment variables from .env file
load_dotenv()
GH_TOKEN = os.getenv("GH_TOKEN")

# Define API constants
GITHUB_API_URL = "https://api.github.com"
BASE_GITHUB_URL = "https://github.com/"
HEADERS = {"Accept": "application/vnd.github.v3+json"}

# If a GitHub token is available, use it for authentication
if GH_TOKEN:
    HEADERS["Authorization"] = f"token {GH_TOKEN}"

RETRY_LIMIT = 10
ITEMS_PER_PAGE = 30
SLEEP_INTERVAL = 1  # Interval between requests to avoid rate limiting
GIT_OUT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "out")

# Increase buffer size for git
# Git().update_environment(GIT_HTTP_MAX_REQUEST_BUFFER='104857600')


def github_api_request(url, params=None):
    retry_count = 0
    while retry_count < RETRY_LIMIT:
        try:
            response = requests.get(url, headers=HEADERS, params=params)
            print(f"Request URL: {response.url}")
            if response.status_code in [403, 429]:
                if (
                    "X-RateLimit-Remaining" in response.headers
                    and response.headers["X-RateLimit-Remaining"] == "0"
                ):
                    reset_time = int(response.headers["X-RateLimit-Reset"])
                    sleep_time = max(0, time.time() - reset_time)
                    print(
                        f"Primary rate limit exceeded. Sleeping for {sleep_time} seconds."
                    )
                    time.sleep(sleep_time + 1)  
                    retry_count = 0 
                    continue
                elif "Retry-After" in response.headers:
                    sleep_time = int(response.headers["Retry-After"])
                    print(
                        f"Secondary rate limit exceeded. Sleeping for {sleep_time} seconds."
                    )
                    time.sleep(sleep_time)
                    retry_count += 1
                    continue
                else:
                    sleep_time = int(pow(2, retry_count))  # Exponential backoff
                    print(
                        f"Secondary rate limit exceeded. Retrying in {sleep_time} seconds."
                    )
                    time.sleep(sleep_time)
                    retry_count += 1
                    if retry_count >= RETRY_LIMIT:
                        raise Exception(
                            "Maximum retries exceeded due to secondary rate limit."
                        )
                    continue
            elif response.status_code == 200:
                time.sleep(SLEEP_INTERVAL)  # Slow down requests to avoid rate limiting
                return response.json()
            elif response.status_code == 451:
                print("Resource is unavailable due to legal reasons (status 451).")
                return None 
            else:
                print(f"Request failed with status {response.status_code}.")
                return None  # Instead of raising an exception, return None
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return None  # Return None in case of any request exception

    # If all retries are done, return None
    return None


class GitHubProfileAnalyzer:
    def __init__(self, username):
        self.exists = False
        self.username = username
        self.profile_data = None
        self.all_repos = []
        self.commits = {}
        self.commit_msgs = defaultdict(list)

        # TODO: Analyze this
        self.followers = []
        self.following = []

        # TODO: Add data to filters
        self.date_filter = []
        self.commit_filter = []
        self.follow_filter = []

        self.user_dir = os.path.join(GIT_OUT_PATH, self.username)
        self.data_file = os.path.join(self.user_dir, f"{self.username}.json")

        # Check if user_dir exists, if not, create it
        if not os.path.exists(self.user_dir):
            os.makedirs(self.user_dir)

        if os.path.exists(self.data_file):
            self.load_existing()
            self.exists = True

    def run_full_analysis(self):
        # NOTE: Works with Github API
        self.fetch_profile_data()
        self.fetch_following()
        self.fetch_followers()
        self.fetch_profile_repos()

        # NOTE: Works with .git data
        self.fetch_from_git_clone()
        self.fetch_commit_messages()

        # NOTE: Filtering all data (must be present)
        self.filter_created_at()

        # NOTE: Save all data
        self.save_output()

    def generate_report(self):
        # Find mutual followers
        mutual_followers = set(f["login"] for f in self.followers) & set(
            f["login"] for f in self.following
        )

        # Find contributors to owner's repos
        contributors = defaultdict(set)
        for repo in self.all_repos:
            if not repo["fork"]:
                repo_name = repo["name"]
                url = f"{GITHUB_API_URL}/repos/{self.username}/{repo_name}/contributors"
                repo_contributors = github_api_request(url)
                if repo_contributors:
                    for contributor in repo_contributors:
                        contributors[repo_name].add(contributor["login"])

        # Find unique emails in commits
        unique_emails = {}
        for repo_name, commits in self.commits.items():
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
        original_repos_count = sum(1 for repo in self.all_repos if not repo["fork"])
        forked_repos_count = sum(1 for repo in self.all_repos if repo["fork"])

        # Check if user has contributed to other repositories via PRs
        search_url = f"{GITHUB_API_URL}/search/issues"
        search_params = {
            "q": f"type:pr author:{self.username}",
            "per_page": ITEMS_PER_PAGE,
        }
        search_results = github_api_request(search_url, search_params)
        pull_requests_to_other_repos = set()

        if search_results and "items" in search_results:
            for item in search_results["items"]:
                repo_name = item["repository_url"].split("/")[-1]
                owner_name = item["repository_url"].split("/")[-2]
                if owner_name != self.username:
                    pull_requests_to_other_repos.add(f"{owner_name}/{repo_name}")

        # Construct full GitHub HTML links for followers and following
        BASE_GITHUB_URL = "https://github.com/"
        followers_list = [f"{BASE_GITHUB_URL}{f['login']}" for f in self.followers]
        following_list = [f"{BASE_GITHUB_URL}{f['login']}" for f in self.following]

        report_data = {
            "mutual_followers": list(mutual_followers),
            "contributors": {repo: list(users) for repo, users in contributors.items()},
            "followers": followers_list,
            "following": following_list,
            "unique_emails": unique_emails,
            "original_repos_count": original_repos_count,
            "forked_repos_count": forked_repos_count,
            "pull_requests_to_other_repos": list(pull_requests_to_other_repos),
        }

        # Check if date_filter is not empty and include it under "potential_copy"
        if self.date_filter:
            report_data["potential_copy"] = self.date_filter

        report_file = os.path.join(self.user_dir, "report.json")
        self.save_to_json(report_data, report_file)

        print(f"Report generated and saved to {report_file}")


    def filter_created_at(self):
        account_created_at = parser.parse(self.profile_data["created_at"])

        for repo_name, commits in self.commits.items():
            if commits:
                first_commit_date = parser.parse(
                    commits[-1]["commit"]["author"]["date"]
                )
                if first_commit_date < account_created_at:
                    self.date_filter.append(
                        {
                            "repo": repo_name,
                            "reason": "account created earlier than the first commit",
                            "commit_date": first_commit_date.isoformat(),
                        }
                    )

    def filter_commit_search(self):
        for repo_name, commits in self.commits.items():
            if commits:
                for commit in commits:
                    commit_message = commit["commit"]["message"]
                    commit_len = len(commit_message)
                    if 20 < commit_len < 150:

                        message = commit_message.replace("\n", " ").replace("\r", " ")

                        search_url = f"{GITHUB_API_URL}/search/commits"
                        search_params = {
                            "q": message,
                            "per_page": ITEMS_PER_PAGE,
                        }

                        try:
                            search_results = github_api_request(
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
                                self.commit_filter.append(
                                    {
                                        "target_repo": repo_name,
                                        "target_commit": commit_message,
                                        "search_results": search_results["total_count"],
                                        "matching_repos": matching_repos,
                                    }
                                )
                        except requests.exceptions.HTTPError as e:
                            print(f"Error fetching search results: {e}")
            else:
                self.commit_filter.append(
                    {
                        "target_repo": repo_name,
                        "target_commit": "No commits found",
                        "search_results": 0,
                        "matching_repos": [],
                    }
                )

        self.save_commit_filter()

    def fetch_profile_data(self):
        url = f"{GITHUB_API_URL}/users/{self.username}"
        self.profile_data = github_api_request(url)

    def fetch_profile_repos(self):
        url = f"{GITHUB_API_URL}/users/{self.username}/repos"
        self.all_repos = github_api_request(url)
        if not self.all_repos:
            self.all_repos = []

    def fetch_followers(self):
        url = f"{GITHUB_API_URL}/users/{self.username}/followers"
        self.followers = github_api_request(url)
        if not self.followers:
            self.followers = []

    def fetch_following(self):
        url = f"{GITHUB_API_URL}/users/{self.username}/following"
        self.following = github_api_request(url)
        if not self.following:
            self.following = []

    def fetch_from_git_clone(self):
        failed_repos = []
        for repo in self.all_repos:
            if not repo["fork"]:
                repo_name = repo["name"]
                clone_url = repo["clone_url"]
                repo_dir = os.path.join(
                    self.user_dir, f"{self.username}_{repo_name}.git"
                )

                if not os.path.exists(repo_dir):
                    try:
                        print("Git clone:", clone_url)
                        git.Repo.clone_from(clone_url, repo_dir, bare=True, depth=100)
                    except git.exc.GitCommandError as e:
                        if "DMCA" in str(e):
                            print(
                                f"Repository {repo_name} is unavailable due to DMCA takedown."
                            )
                            failed_repos.append(
                                {
                                    "repo_name": repo_name,
                                    "clone_url": clone_url,
                                    "reason": "DMCA takedown",
                                }
                            )
                        else:
                            print(f"fetch_from_git_clone() error in {repo_name}: {e}")
                            failed_repos.append(
                                {
                                    "repo_name": repo_name,
                                    "clone_url": clone_url,
                                    "reason": str(e),
                                }
                            )

                if os.path.exists(repo_dir):
                    self.commits[repo_name] = self.fetch_repo_commits(repo_dir)

        self.save_failed_repos(failed_repos)

    def fetch_repo_commits(self, repo_dir):
        try:
            repo = git.Repo(repo_dir)
            commit_data = []
            for commit in repo.iter_commits():
                repo_name = (
                    os.path.basename(repo_dir)
                    .replace(f"{self.username}_", "")
                    .replace(".git", "")
                )
                commit_info = {
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
                    "url": f"https://github.com/{self.username}/{repo_name}/commit/{commit.hexsha}",
                }
                commit_data.append(commit_info)
            return commit_data
        except git.exc.NoSuchPathError as e:
            print(f"fetch_repo_commits() Path error: {e}")
            return []

    def fetch_commit_messages(self):
        for repo_name, commits in self.commits.items():
            if commits:
                for commit in commits:
                    # NOTE: Only commit messages
                    self.commit_msgs[repo_name].append(commit["commit"]["message"])
            else:
                self.commit_msgs[repo_name] = []

    def save_output(self):
        all_data = {
            "profile_data": self.profile_data,
            "repos": self.all_repos,
            "commits": dict(self.commits),
            "commits_msgs": dict(self.commit_msgs),
            "followers": self.followers,
            "following": self.following,
            "date_filter": self.date_filter,
            "commit_filter": self.commit_filter,
        }

        self.save_to_json(all_data, self.data_file)

    def load_existing(self):
        with open(self.data_file, "r") as json_file:
            data = json.load(json_file)
            self.profile_data = data.get("profile_data")
            self.all_repos = data.get("repos", [])
            self.commits = defaultdict(list, data.get("commits", {}))
            self.commit_msgs = defaultdict(list, data.get("commits", {}))
            self.followers = data.get("followers", [])
            self.following = data.get("following", [])
            self.date_filter = data.get("date_filter", [])
            self.commit_filter = data.get("commit_filter", [])

    def save_commit_filter(self):
        if self.data_file is None:
            print("No data file exsits.")
            return

        with open(self.data_file, "r") as json_file:
            data = json.load(json_file)
            data["commit_filter"] = self.commit_filter
            self.save_to_json(data, self.data_file)

    def save_failed_repos(self, failed_repos):
        failed_repos_file = os.path.join(self.user_dir, "failed_repos.json")
        with open(failed_repos_file, "w") as json_file:
            json.dump(failed_repos, json_file, indent=4)

    def save_to_json(self, data, filename):
        with open(filename, "w") as json_file:
            json.dump(data, json_file, indent=4)


# Parse command-line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(description="Analyze a GitHub profile.")
    parser.add_argument("username", type=str, help="GitHub username to analyze")
    parser.add_argument(
        "--commit_search",
        action="store_true",
        help="Query GH API search for similar commits",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    analyzer = GitHubProfileAnalyzer(args.username)
    start_time = time.time()

    if not analyzer.exists:
        print("Analyzing profile data...")
        analyzer.run_full_analysis()
    else:
        print("Profile data already exists.")

    if args.commit_search:
        print("Searching for copied commits...")
        analyzer.filter_commit_search()
    else:
        print("No commit search requested.")

    print("Generating report...")
    analyzer.generate_report()

    end_time = time.time()
    print(f"Analysis completed in {end_time - start_time:.2f} seconds.")
