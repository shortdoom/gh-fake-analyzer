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

# Define API constants
GITHUB_API_URL = "https://api.github.com"
BASE_GITHUB_URL = "https://github.com/"
HEADERS = {"Accept": "application/vnd.github.v3+json"}

# If a GitHub token is available, use it for authentication
if GH_TOKEN:
    HEADERS["Authorization"] = f"token {GH_TOKEN}"

RETRY_LIMIT = 10
ITEMS_PER_PAGE = 100
SLEEP_INTERVAL = 1  # Be polite to the API
GIT_OUT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "out")


def github_api_request(url, params=None):
    retry_count = 0
    while retry_count < RETRY_LIMIT:
        try:
            response = requests.get(url, headers=HEADERS, params=params)
            print(f"Request URL: {response.url}")
            logging.info(f"Request URL: {response.url}")
            if response.status_code in [403, 429]:
                if (
                    "X-RateLimit-Remaining" in response.headers
                    and response.headers["X-RateLimit-Remaining"] == "0"
                ):
                    reset_time = int(response.headers["X-RateLimit-Reset"])
                    sleep_time = max(0, reset_time - time.time())
                    print(
                        f"Primary rate limit exceeded. Sleeping for {sleep_time} seconds."
                    )
                    logging.warning(
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
                    logging.warning(
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
                    logging.warning(
                        f"Secondary rate limit exceeded. Retrying in {sleep_time} seconds."
                    )
                    time.sleep(sleep_time)
                    retry_count += 1
                    if retry_count >= RETRY_LIMIT:
                        logging.error(
                            "Maximum retries exceeded due to secondary rate limit."
                        )
                        raise Exception(
                            "Maximum retries exceeded due to secondary rate limit."
                        )
                    continue
            elif response.status_code == 200:
                time.sleep(SLEEP_INTERVAL)  # Slow down requests to avoid rate limiting
                return response.json(), response.headers
            elif response.status_code == 451:
                print("Resource is unavailable due to legal reasons (status 451).")
                logging.error(
                    "Resource is unavailable due to legal reasons (status 451)."
                )
                return None, None
            else:
                print(f"Request failed with status {response.status_code}.")
                logging.error(f"Request failed with status {response.status_code}.")
                return None, None
        except requests.exceptions.RequestException as e:
            logging.error(f"An error occurred: {e}")
            return None, None

    # If all retries are done, return None
    return None, None


def fetch_all_pages(url, params=None):
    results = []
    while url:
        response, headers = github_api_request(url, params)
        if response:
            if isinstance(response, dict) and "items" in response:
                results.extend(response["items"])
            else:
                results.extend(response)
            if "Link" in headers:
                links = requests.utils.parse_header_links(headers["Link"])
                url = None
                for link in links:
                    if link["rel"] == "next":
                        url = link["url"]
                        params = None
                        break
            else:
                break
        else:
            break
    return results


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
        try:
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
        except Exception as e:
            logging.error(f"Error in run_full_analysis: {e}")

    def generate_report(self):
        try:
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
                    repo_contributors = fetch_all_pages(url)
                    if repo_contributors:
                        for contributor in repo_contributors:
                            contributors[repo_name].add(contributor["login"])

            # Classify repos as forked or original
            repo_list = [repo["name"] for repo in self.all_repos if not repo["fork"]]
            forked_repo_list = [repo["name"] for repo in self.all_repos if repo["fork"]]

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
            pull_requests_to_other_repos = {}
            search_results = fetch_all_pages(search_url, search_params)

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
            search_commits_url = f"{GITHUB_API_URL}/search/commits"
            search_commits_params = {
                "q": f"author:{self.username}",
                "per_page": ITEMS_PER_PAGE,
            }
            commits_to_other_repos = {}
            search_commits_results = fetch_all_pages(
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
            followers_list = [f"{BASE_GITHUB_URL}{f['login']}" for f in self.followers]
            following_list = [f"{BASE_GITHUB_URL}{f['login']}" for f in self.following]
            
            # Extract desired fields from profile_data
            profile_info = {
                "login": self.profile_data["login"],
                "id": self.profile_data["id"],
                "node_id": self.profile_data["node_id"],
                "avatar_url": self.profile_data["avatar_url"],
                "html_url": self.profile_data["html_url"],
                "type": self.profile_data["type"],
                "site_admin": self.profile_data["site_admin"],
                "name": self.profile_data["name"],
                "company": self.profile_data.get("company"),
                "blog": self.profile_data.get("blog"),
                "location": self.profile_data.get("location"),
                "email": self.profile_data.get("email"),
                "hireable": self.profile_data.get("hireable"),
                "bio": self.profile_data.get("bio"),
                "twitter_username": self.profile_data.get("twitter_username"),
                "public_repos": self.profile_data["public_repos"],
                "public_gists": self.profile_data["public_gists"],
                "followers": self.profile_data["followers"],
                "following": self.profile_data["following"],
                "created_at": self.profile_data["created_at"],
                "updated_at": self.profile_data["updated_at"]
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

            # Check if date_filter is not empty and include it under "potential_copy"
            if self.date_filter:
                report_data["potential_copy"] = self.date_filter

            report_file = os.path.join(self.user_dir, "report.json")
            self.save_to_json(report_data, report_file)

            logging.info(f"Report generated and saved to {report_file}")
        except Exception as e:
            logging.error(f"Error in generate_report: {e}")

    def filter_created_at(self):
        try:
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
                                "reason": "account creation date later than the first commit to the repository",
                                "commit_date": first_commit_date.isoformat(),
                            }
                        )
        except Exception as e:
            logging.error(f"Error in filter_created_at: {e}")

    def filter_commit_search(self):
        try:
            for repo_name, commits in self.commits.items():
                if commits:
                    for commit in commits:
                        commit_message = commit["commit"]["message"]
                        commit_len = len(commit_message)
                        if 20 < commit_len < 150:
                            message = commit_message.replace("\n", " ").replace(
                                "\r", " "
                            )

                            search_url = f"{GITHUB_API_URL}/search/commits"
                            search_params = {
                                "q": message,
                                "per_page": ITEMS_PER_PAGE,
                            }

                            try:
                                search_results, _ = github_api_request(
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
                                            "search_results": search_results[
                                                "total_count"
                                            ],
                                            "matching_repos": matching_repos,
                                        }
                                    )
                            except requests.exceptions.HTTPError as e:
                                logging.error(f"Error fetching search results: {e}")
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
        except Exception as e:
            logging.error(f"Error in filter_commit_search: {e}")

    def fetch_profile_data(self):
        try:
            url = f"{GITHUB_API_URL}/users/{self.username}"
            self.profile_data, _ = github_api_request(url)
        except Exception as e:
            logging.error(f"Error in fetch_profile_data: {e}")

    def fetch_profile_repos(self):
        try:
            url = f"{GITHUB_API_URL}/users/{self.username}/repos"
            repos = fetch_all_pages(url, {"per_page": ITEMS_PER_PAGE})
            self.all_repos = repos
            if not self.all_repos:
                self.all_repos = []
        except Exception as e:
            logging.error(f"Error in fetch_profile_repos: {e}")

    def fetch_followers(self):
        try:
            url = f"{GITHUB_API_URL}/users/{self.username}/followers"
            followers = fetch_all_pages(url, {"per_page": ITEMS_PER_PAGE})
            self.followers = followers
            if not self.followers:
                self.followers = []
        except Exception as e:
            logging.error(f"Error in fetch_followers: {e}")

    def fetch_following(self):
        try:
            url = f"{GITHUB_API_URL}/users/{self.username}/following"
            following = fetch_all_pages(url, {"per_page": ITEMS_PER_PAGE})
            self.following = following
            if not self.following:
                self.following = []
        except Exception as e:
            logging.error(f"Error in fetch_following: {e}")

    def fetch_from_git_clone(self):
        failed_repos = []
        try:
            for repo in self.all_repos:
                if not repo["fork"]:
                    repo_name = repo["name"]
                    clone_url = repo["clone_url"]
                    repo_dir = os.path.join(
                        self.user_dir, f"{self.username}_{repo_name}.git"
                    )

                    if not os.path.exists(repo_dir):
                        try:
                            print(f"Git clone: {clone_url}")
                            logging.info(f"Git clone: {clone_url}")
                            git.Repo.clone_from(
                                clone_url, repo_dir, bare=True, depth=100
                            )
                        except git.exc.GitCommandError as e:
                            if "DMCA" in str(e):
                                print(
                                    f"Repository {repo_name} is unavailable due to DMCA takedown."
                                )
                                logging.error(
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
                                print(f"Error in {repo_name}: {e}")
                                logging.error(
                                    f"fetch_from_git_clone() error in {repo_name}: {e}"
                                )
                                failed_repos.append(
                                    {
                                        "repo_name": repo_name,
                                        "clone_url": clone_url,
                                        "reason": str(e),
                                    }
                                )

                    if os.path.exists(repo_dir):
                        self.commits[repo_name] = self.fetch_repo_commits(repo_dir)
                        try:
                            shutil.rmtree(repo_dir)
                            logging.info(f"Deleted {repo_dir}")
                        except Exception as e:
                            logging.error(f"Error deleting {repo_dir}: {e}")

        except Exception as e:
            logging.error(f"Error in fetch_from_git_clone: {e}")
        finally:
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
            logging.error(f"fetch_repo_commits() Path error: {e}")
            return []

    def fetch_commit_messages(self):
        try:
            for repo_name, commits in self.commits.items():
                if commits:
                    for commit in commits:
                        # NOTE: Only commit messages
                        self.commit_msgs[repo_name].append(commit["commit"]["message"])
                else:
                    self.commit_msgs[repo_name] = []
        except Exception as e:
            logging.error(f"Error in fetch_commit_messages: {e}")

    def save_output(self):
        try:
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
        except Exception as e:
            logging.error(f"Error in save_output: {e}")

    def load_existing(self):
        try:
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
        except Exception as e:
            logging.error(f"Error in load_existing: {e}")

    def save_commit_filter(self):
        try:
            if self.data_file is None:
                logging.error("No data file exists.")
                return

            with open(self.data_file, "r") as json_file:
                data = json.load(json_file)
                data["commit_filter"] = self.commit_filter
                self.save_to_json(data, self.data_file)
        except Exception as e:
            logging.error(f"Error in save_commit_filter: {e}")

    def save_failed_repos(self, failed_repos):
        try:
            failed_repos_file = os.path.join(self.user_dir, "failed_repos.json")
            with open(failed_repos_file, "w") as json_file:
                json.dump(failed_repos, json_file, indent=4)
        except Exception as e:
            logging.error(f"Error in save_failed_repos: {e}")

    def save_to_json(self, data, filename):
        try:
            with open(filename, "w") as json_file:
                json.dump(data, json_file, indent=4)
        except Exception as e:
            logging.error(f"Error in save_to_json: {e}")


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

    try:
        if not analyzer.exists:
            logging.info("Analyzing profile data...")
            analyzer.run_full_analysis()
        else:
            logging.info("Profile data already exists.")

        if args.commit_search:
            logging.info("Searching for copied commits...")
            analyzer.filter_commit_search()
        else:
            logging.info("No commit search requested.")

        logging.info("Generating report...")
        analyzer.generate_report()

    except Exception as e:
        logging.error(f"Error in main execution: {e}")

    end_time = time.time()
    print(f"Analysis completed in {end_time - start_time:.2f} seconds.")
    logging.info(f"Analysis completed in {end_time - start_time:.2f} seconds.")
