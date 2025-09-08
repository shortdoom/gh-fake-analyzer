import csv
import logging
import os
import datetime
from typing import List, Dict, Set
from ..utils.api import APIUtils
from ..modules.fetch import GithubFetchManager
from ..modules.monitor import GitHubMonitor
from ..utils.data import DataManager

# NOTE: gh-analyze --tool check_activity --targets targets/crypto-ecosystem-activity-debug

# Produces TOOL_CHECK_ACTIVITY_<timestamp>/activity_check.csv with the following columns:

# repository,username,suspicious,high_following_count,high_followers_count,target_contributors_list,follows_target_users_list,fork_target_contributors_list,target_orgs,large_orgs,pr_count,pr_list,pr_check_triggered_by,target_org_member,large_org_member,high_following,high_followers,follows_target_users,has_target_contributors,has_fork_target_contributors


# List of organizations to check for membership
# TODO: make this configurable
TARGET_ORGS = {
    "jazzband", "dev-protocol", "EddieHubCommunity", "Alphasian", "openAOD",
    "Design-and-Code", "WarriorWhoCodes", "App-Choreography", "Jaidevstudio",
    "WebXDAO", "CommunityPro", "Devs-Dungeon", "infraform", "accessibleForAll",
    "yfosp", "fearlesstech"
}

# Load target usernames from debug file
def load_target_usernames() -> List[str]:
    """Load target usernames from the debug file."""
    debug_file = os.path.join("targets", "connections_filter", "usernames")
    try:
        with open(debug_file, 'r') as f:
            # Read lines and clean up usernames - remove commas, spaces, and empty lines
            usernames = [line.strip().strip(',').strip() for line in f.readlines()]
            # Filter out empty lines and return non-empty usernames
            return [username for username in usernames if username]
    except Exception as e:
        logging.error(f"Error loading target usernames: {e}")
        return []

def check_activity(usernames: List[str], output_file: str = "activity_check.csv") -> None:
    """
    Check recent activity, organization membership, and follower counts for a list of GitHub usernames.
    Outputs results to a CSV file with detailed event information and flags.
    
    Args:
        usernames (List[str]): List of GitHub usernames to check
        output_file (str): Name of the output CSV file (will be saved in /out directory)
    """
    try:
        api_utils = APIUtils()
        github_fetch = GithubFetchManager(api_utils)
        monitor = GitHubMonitor(api_utils)
        
        # Initialize DataManager for output directory handling
        directory_name = "TOOL_CHECK_ACTIVITY_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        data_manager = DataManager(directory_name)
        
        # Load target usernames for relationship checks
        target_usernames = load_target_usernames()
        
        # Clean usernames to remove any trailing spaces
        usernames = [username.strip() for username in usernames]
        
        results = []
        
        for username in usernames:
            logging.info(f"Checking activity for {username}...")
            
            # Initialize result with default values
            result = {
                "username": username,
                "suspicious": "false",
                "high_following_count": "",
                "high_followers_count": "",
                "target_contributors_list": "",
                "follows_target_users_list": "",
                "target_orgs": "",
                "large_orgs": "",
                "fork_target_contributors_list": "",
                "target_org_member": "false",
                "large_org_member": "false",
                "high_following": "false",
                "high_followers": "false",
                "follows_target_users": "false",
                "has_target_contributors": "false",
                "has_fork_target_contributors": "false",
            }
                        
            # Get user's organizations and check membership
            try:
                user_orgs = github_fetch.fetch_user_organizations(username)
                target_orgs_found = []
                large_orgs_found = []
                
                for org in user_orgs:
                    org_name = org.get("login", "").lower()
                    if org_name in TARGET_ORGS:
                        target_orgs_found.append(org_name)
                    else:
                        # Check if organization has more than 100 members
                        member_count = github_fetch.fetch_organization_members_count(org_name)
                        if member_count and member_count > 100:
                            large_orgs_found.append(org_name)
                
                if target_orgs_found:
                    result["target_org_member"] = "true"
                    result["target_orgs"] = ",".join(target_orgs_found)
                
                if large_orgs_found:
                    result["large_org_member"] = "true"
                    result["large_orgs"] = ",".join(large_orgs_found)
                    
            except Exception as e:
                logging.error(f"Error checking organizations for {username}: {e}")
            
            # Check follower/following counts
            try:
                profile_data = github_fetch.fetch_profile_data(username)
                if profile_data:
                    following_count = profile_data.get("following", 0)
                    followers_count = profile_data.get("followers", 0)
                    
                    if following_count > 200:
                        result["high_following"] = "true"
                        result["high_following_count"] = following_count
                    if followers_count > 200:
                        result["high_followers"] = "true"
                        result["high_followers_count"] = followers_count
                        
            except Exception as e:
                logging.error(f"Error checking follower counts for {username}: {e}")
            
            # Check relationships with target usernames
            try:
                relationships = github_fetch.check_user_relationships(username, target_usernames)
                
                if relationships["following"]:
                    result["follows_target_users"] = "true"
                    result["follows_target_users_list"] = ",".join(relationships["following"])
                
                if relationships["contributors"]:
                    result["has_target_contributors"] = "true"
                    result["target_contributors_list"] = ",".join(relationships["contributors"])
                
                if relationships["fork_target_contributors"]:
                    result["has_fork_target_contributors"] = "true"
                    # Format: "username1:repo1,username2:repo2"
                    result["fork_target_contributors_list"] = ",".join(
                        f"{username}:{repo}" for username, repo in relationships["fork_target_contributors"]
                    )
                
                # Set suspicious flag from relationships check
                result["suspicious"] = relationships["suspicious"]
                    
            except Exception as e:
                logging.error(f"Error checking user relationships for {username}: {e}")
            
            results.append(result)
            logging.info(f"Completed check for {username}")
        
        # Write results to CSV in the /out directory
        fieldnames = [
            "username",
            "suspicious",
            "high_following_count",
            "high_followers_count",
            "target_contributors_list",
            "follows_target_users_list",
            "target_orgs",
            "large_orgs",
            "fork_target_contributors_list",
            "target_org_member",
            "large_org_member",
            "high_following",
            "high_followers",
            "follows_target_users",
            "has_target_contributors",
            "has_fork_target_contributors",
        ]
        
        output_path = os.path.join(data_manager.user_dir, output_file)
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
            
        logging.info(f"Results written to {output_path}")
        
    except Exception as e:
        logging.error(f"Error in check_activity: {e}")
        raise