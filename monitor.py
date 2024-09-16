import argparse
import requests
import time
import os
import json
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    filename="monitoring.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Also log to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger("").addHandler(console)

# Load environment variables from .env file
load_dotenv()
GH_TOKEN = os.getenv("GH_TOKEN")

if not GH_TOKEN:
    logging.error(
        "GitHub token not found. Make sure GH_TOKEN is set in your .env file."
    )
    exit(1)


class APIUtils:
    GITHUB_API_URL = "https://api.github.com"
    HEADERS = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {GH_TOKEN}",
    }
    RETRY_LIMIT = 3

    @classmethod
    def github_api_request(cls, url, params=None, etag=None):
        headers = cls.HEADERS.copy()
        if etag:
            headers["If-None-Match"] = etag

        retry_count = 0
        while retry_count < cls.RETRY_LIMIT:
            try:
                response = requests.get(url, headers=headers, params=params)
                if response.status_code == 304:
                    return None, response.headers
                elif response.status_code == 200:
                    return response.json(), response.headers
                elif response.status_code == 401:
                    logging.error("Authentication failed. Check your GitHub token.")
                    exit(1)
                elif response.status_code in [403, 429]:
                    cls._handle_rate_limit(response)
                    retry_count += 1
                    continue
                else:
                    logging.error(f"Request failed with status {response.status_code}.")
                    return None, None
            except requests.exceptions.RequestException as e:
                logging.error(f"An error occurred: {e}")
                return None, None

        return None, None

    @classmethod
    def _handle_rate_limit(cls, response):
        if (
            "X-RateLimit-Remaining" in response.headers
            and int(response.headers["X-RateLimit-Remaining"]) == 0
        ):
            reset_time = int(response.headers["X-RateLimit-Reset"])
            sleep_time = max(0, reset_time - time.time())
            logging.warning(f"Rate limit exceeded. Sleeping for {sleep_time} seconds.")
            time.sleep(sleep_time + 1)
        elif "Retry-After" in response.headers:
            sleep_time = int(response.headers["Retry-After"])
            logging.warning(
                f"Secondary rate limit encountered. Sleeping for {sleep_time} seconds."
            )
            time.sleep(sleep_time)
        else:
            logging.warning("Rate limit encountered. Sleeping for 60 seconds.")
            time.sleep(60)


def fetch_user_events(username, etag=None):
    url = f"{APIUtils.GITHUB_API_URL}/users/{username}/events"
    events, headers = APIUtils.github_api_request(url, etag=etag)

    new_etag = headers.get("ETag") if headers else None
    poll_interval = int(headers.get("X-Poll-Interval", 60)) if headers else 60

    return events, new_etag, poll_interval


def fetch_user_info(username):
    url = f"{APIUtils.GITHUB_API_URL}/users/{username}"
    user_info, _ = APIUtils.github_api_request(url)
    return user_info


def fetch_user_following(username):
    url = f"{APIUtils.GITHUB_API_URL}/users/{username}/following"
    following, _ = APIUtils.github_api_request(url)
    return following


def clean_user_info(user_info):
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
    return {k: v for k, v in user_info.items() if k not in KEYS_TO_REMOVE}


def clean_event(event):
    return {
        "id": event.get("id"),
        "type": event.get("type"),
        "actor": {
            "id": event["actor"].get("id"),
            "login": event["actor"].get("login"),
            "display_login": event["actor"].get("display_login"),
            "gravatar_id": event["actor"].get("gravatar_id"),
            "url": event["actor"].get("url"),
            "avatar_url": event["actor"].get("avatar_url"),
        },
        "repo": {
            "id": event["repo"].get("id"),
            "name": event["repo"].get("name"),
            "url": event["repo"].get("url"),
        },
        "payload": event.get("payload", {}),
        "public": event.get("public"),
        "created_at": event.get("created_at"),
    }


def interpret_event(event):
    event_type = event.get("type")
    actor = event.get("actor", {}).get("login")
    repo = event.get("repo", {}).get("name")
    payload = event.get("payload", {})

    interpretations = {
        "WatchEvent": f"{actor} starred the repository {repo}",
        "PushEvent": f"{actor} pushed to {repo}. Commits: {len(payload.get('commits', []))}",
        "CreateEvent": f"{actor} created a {payload.get('ref_type')} in {repo}",
        "DeleteEvent": f"{actor} deleted a {payload.get('ref_type')} in {repo}",
        "ForkEvent": f"{actor} forked {repo}",
        "IssuesEvent": f"{actor} {payload.get('action')} an issue in {repo}",
        "IssueCommentEvent": f"{actor} commented on an issue in {repo}",
        "PullRequestEvent": f"{actor} {payload.get('action')} a pull request in {repo}",
        "PullRequestReviewEvent": f"{actor} reviewed a pull request in {repo}",
        "PullRequestReviewCommentEvent": f"{actor} commented on a pull request review in {repo}",
        "CommitCommentEvent": f"{actor} commented on a commit in {repo}",
        "ReleaseEvent": f"{actor} {payload.get('action')} a release in {repo}",
        "PublicEvent": f"{actor} made {repo} public",
        "MemberEvent": f"{actor} {payload.get('action')} a member in {repo}",
        "GollumEvent": f"{actor} updated the wiki in {repo}",
    }

    return interpretations.get(event_type, f"Unknown event type: {event_type}")


def process_events(events):
    if not events:
        return []

    processed_events = []
    for event in events:
        event_type = event.get("type")
        repo = event.get("repo", {}).get("name")
        created_at = event.get("created_at")
        description = interpret_event(event)

        processed_events.append(
            {
                "type": event_type,
                "target": repo,
                "date": created_at,
                "description": description,
            }
        )

    return processed_events


def monitor_user_activity(username, etag=None, last_check=None):
    events, new_etag, poll_interval = fetch_user_events(username, etag)

    if events is None and new_etag == etag:
        return None, new_etag, poll_interval  # No new events

    processed_events = process_events(events)

    if last_check:
        processed_events = [
            e
            for e in processed_events
            if datetime.strptime(e["date"], "%Y-%m-%dT%H:%M:%SZ") > last_check
        ]

    return processed_events, new_etag, poll_interval


def main():
    parser = argparse.ArgumentParser(description="Monitor GitHub user activity.")
    parser.add_argument(
        "-t", "--targets", help="File containing target usernames, one per line"
    )
    parser.add_argument("-u", "--username", help="Single GitHub username to monitor")
    args = parser.parse_args()

    if not args.targets and not args.username:
        parser.error("Either --targets or --username must be provided")

    targets = (
        [args.username]
        if args.username
        else [line.strip() for line in open(args.targets)]
    )

    user_data = {
        username: {
            "etag": None,
            "last_check": None,
            "last_info_check": None,
            "following_count": 0,
            "name": None,
            "company": None,
            "blog": None,
            "location": None,
            "email": None,
            "bio": None,
            "twitter_username": None,
            "updated_at": None,
        }
        for username in targets
    }

    logging.info(f"Starting to monitor activity for users: {', '.join(targets)}")
    logging.info("Press Ctrl+C to stop monitoring.")

    try:
        while True:
            for username in targets:
                current_time = datetime.now()

                # Check for new events
                events, new_etag, poll_interval = monitor_user_activity(
                    username,
                    etag=user_data[username]["etag"],
                    last_check=user_data[username]["last_check"],
                )

                user_data[username]["etag"] = new_etag
                user_data[username]["last_check"] = current_time

                if events:
                    for event in events:
                        log_message = f"User: {username}, {event['description']}, Date: {event['date']}"
                        logging.info(log_message)

                # Check for user info changes every hour
                if user_data[username]["last_info_check"] is None or (
                    current_time - user_data[username]["last_info_check"]
                ) > timedelta(minutes=10):
                    user_info = fetch_user_info(username)
                    if user_info:
                        # Check for new following
                        new_following_count = user_info.get("following", 0)
                        if new_following_count > user_data[username]["following_count"]:
                            new_following = fetch_user_following(username)
                            if new_following:
                                for followed in new_following[
                                    : new_following_count
                                    - user_data[username]["following_count"]
                                ]:
                                    log_message = f"User: {username} is now following {followed['login']}"
                                    logging.info(log_message)
                            user_data[username]["following_count"] = new_following_count

                        # Check for changes in other user info fields
                        fields_to_check = [
                            "name",
                            "company",
                            "blog",
                            "location",
                            "email",
                            "bio",
                            "twitter_username",
                            "updated_at",
                        ]
                        for field in fields_to_check:
                            new_value = user_info.get(field)
                            if new_value != user_data[username][field]:
                                if field == "updated_at":
                                    log_message = f"User: {username} profile was updated at {new_value}"
                                else:
                                    log_message = f"User: {username} changed their {field} from '{user_data[username][field]}' to '{new_value}'"
                                logging.info(log_message)
                                user_data[username][field] = new_value

                    user_data[username]["last_info_check"] = current_time

                time.sleep(poll_interval)

    except KeyboardInterrupt:
        logging.info("Stopping user activity monitoring.")


if __name__ == "__main__":
    main()
