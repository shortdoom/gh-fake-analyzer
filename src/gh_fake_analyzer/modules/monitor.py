import time
import logging
from datetime import datetime, timedelta
from ..utils.config import setup_logging, MONITOR_SLEEP
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from .fetch import GithubFetchManager

@dataclass
class UserEventData:
    etag: Optional[str] = None
    last_check: Optional[datetime] = None
    last_info_check: Optional[datetime] = None
    following_count: int = 0
    name: Optional[str] = None
    company: Optional[str] = None
    blog: Optional[str] = None
    location: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None
    twitter_username: Optional[str] = None
    updated_at: Optional[str] = None

class GitHubMonitor:
    def __init__(self, api_utils):
        self.api_utils = api_utils
        self.github_fetch = GithubFetchManager(api_utils)
        setup_logging("monitoring.log")
        self.logger = logging.getLogger('monitoring')
        
    @staticmethod
    def interpret_event(event: Dict) -> str:
        """Convert a GitHub event into a human-readable description."""
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
        
    def fetch_user_events(self, username: str, etag: Optional[str] = None) -> Tuple[List[Dict], Optional[str], int]:
        return self.github_fetch.fetch_user_events(username, etag)
    
    def fetch_user_info(self, username: str) -> Dict:
        return self.github_fetch.fetch_profile_data(username)
    
    def fetch_user_following(self, username: str) -> List[Dict]:
        return self.github_fetch.fetch_following(username)

    def process_events(self, events: List[Dict]) -> List[Dict]:
        """Process raw GitHub events into a standardized format."""
        if not events:
            return []

        return [{
            "type": event.get("type"),
            "target": event.get("repo", {}).get("name"),
            "date": event.get("created_at"),
            "description": self.interpret_event(event)
        } for event in events]

    def recent_events(self, username: str) -> List[Dict]:
        """Fetch and process events from the last specified number of days."""
        events, _, _ = self.fetch_user_events(username)
        if not events:
            return []
        
        return self.process_events(events)

    def monitor_user_changes(self, username: str, user_data: UserEventData) -> List[str]:
        """Monitor changes in user profile and following."""
        current_time = datetime.now()
        changes = []
        
        if user_data.last_info_check is None or (
            current_time - user_data.last_info_check > timedelta(minutes=MONITOR_SLEEP)
        ):
            user_info = self.fetch_user_info(username)
            if user_info:
                # Check for new following
                new_following_count = user_info.get("following", 0)
                if new_following_count > user_data.following_count:
                    new_following = self.fetch_user_following(username)
                    for followed in new_following[:new_following_count - user_data.following_count]:
                        changes.append(f"User: {username} is now following {followed['login']}")
                    user_data.following_count = new_following_count

                # Check profile changes
                fields_to_check = [
                    "name", "company", "blog", "location", "email", 
                    "bio", "twitter_username", "updated_at"
                ]
                
                for field in fields_to_check:
                    new_value = user_info.get(field)
                    old_value = getattr(user_data, field)
                    if new_value != old_value:
                        if field == "updated_at":
                            changes.append(f"User: {username} profile was updated at {new_value}")
                        else:
                            changes.append(
                                f"User: {username} changed their {field} "
                                f"from '{old_value}' to '{new_value}'"
                            )
                        setattr(user_data, field, new_value)

            user_data.last_info_check = current_time
            
        return changes

    def monitor(self, targets: List[str]) -> None:
        """Live monitor GitHub activity for specified users."""
        if not targets:
            self.logger.info("No target(s) for monitor specified")
            return

        user_data = {username: UserEventData() for username in targets}
        
        self.logger.info(f"Starting to monitor activity for users: {', '.join(targets)}")
        self.logger.info("Press Ctrl+C to stop monitoring.")

        try:
            while True:
                for username in targets:
                    current_time = datetime.now()
                    data = user_data[username]

                    # Check for new events
                    events, new_etag, poll_interval = self.fetch_user_events(
                        username, etag=data.etag
                    )
                    
                    data.etag = new_etag
                    data.last_check = current_time

                    if events:
                        processed_events = self.process_events(events)
                        for event in processed_events:
                            self.logger.info(f"User: {username}, {event['description']}, Date: {event['date']}")

                    # Check for profile changes
                    changes = self.monitor_user_changes(username, data)
                    for change in changes:
                        self.logger.info(change)

                    time.sleep(poll_interval)

        except KeyboardInterrupt:
            self.logger.info("Stopping user activity monitoring.")
