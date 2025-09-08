import os
import csv
import logging
from datetime import datetime
from typing import List, Union
from ..utils.api import APIUtils
from ..modules.fetch import GithubFetchManager

def get_external_prs(usernames: Union[str, List[str]], out_path: str = None):
    """
    Fetch all external PRs (not to user's own repos) for a username or list of usernames.
    Output a CSV with columns: username, pr, date (date PR was made).
    CSV is saved in a new directory TOOL_EXTERNAL_PR.
    """
    if isinstance(usernames, str):
        usernames = [usernames]

    api_utils = APIUtils()
    github_fetch = GithubFetchManager(api_utils)

    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"TOOL_EXTERNAL_PR_{timestamp}"
    if out_path:
        output_dir = os.path.join(out_path, dir_name)
    else:
        output_dir = os.path.join("out", dir_name)
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "external_prs.csv")

    fieldnames = ["username", "pr", "date"]
    rows = []

    for username in usernames:
        logging.info(f"Fetching external PRs for {username}...")
        try:
            pr_results = github_fetch.search_pull_requests(username)
            for pr in pr_results:
                repo_owner = pr["repository_url"].split("/")[-2]
                if repo_owner.lower() != username.lower():
                    pr_url = pr.get("html_url", "")
                    pr_date = pr.get("created_at", "")
                    rows.append({
                        "username": username,
                        "pr": pr_url,
                        "date": pr_date
                    })
        except Exception as e:
            logging.error(f"Error fetching PRs for {username}: {e}")

    with open(output_file, "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logging.info(f"External PRs written to {output_file}") 