import os
import json
import logging
from ..utils.data import DataManager


class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def format_value(value, indent=0):
    """
    Format a value for pretty printing
    """
    indent_str = "  " * indent

    if isinstance(value, list):
        if not value:
            return "[]"

        # Check if list contains dictionaries
        if any(isinstance(item, dict) for item in value):
            items = [f"{indent_str}  {json.dumps(item, indent=2)}" for item in value]
            return "[\n" + ",\n".join(items) + f"\n{indent_str}]"

        # For simple lists, format them more compactly but still readable
        items = [f"{indent_str}  {json.dumps(item)}" for item in value]
        return "[\n" + ",\n".join(items) + f"\n{indent_str}]"

    elif isinstance(value, dict):
        return json.dumps(value, indent=2)

    return json.dumps(value)


def get_nested_value(data, key_path):
    """
    Retrieve nested dictionary value using dot notation
    Example: profile_info.login -> data['profile_info']['login']
    """
    keys = key_path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


def print_summary(data):
    """Print top-level summary of profile data"""
    print(f"{Colors.BLUE}Name:{Colors.RESET} {data['profile_info']['name']}")
    print(f"{Colors.BLUE}Profile ID:{Colors.RESET} {data['profile_info']['id']}")
    print(f"{Colors.BLUE}URL:{Colors.RESET} {data['profile_info']['html_url']}")
    print(f"{Colors.BLUE}Created At:{Colors.RESET} {data['profile_info']['created_at']}")
    print(f"{Colors.BLUE}Updated At:{Colors.RESET} {data['profile_info']['updated_at']}")
    print(f"{Colors.BLUE}Followers/Following:{Colors.RESET} ({data['profile_info']['followers']}/{data['profile_info']['following']})")
    
    # Get mutual following list
    mutual_following = sorted(data['mutual_followers'])
    mutual_count = len(mutual_following)
    first_10_mutual = mutual_following[:10]
    mutual_list = ', '.join(first_10_mutual)
    if mutual_count > 10:
        mutual_list += ' <cut+10>'
    print(f"{Colors.BLUE}Mutual Following:{Colors.RESET} {mutual_count} [{mutual_list}]")
    
    print(f"{Colors.BLUE}Repositories/Forks:{Colors.RESET} ({data['original_repos_count']}/{data['forked_repos_count']})")
    print(f"{Colors.BLUE}Issues/Comments:{Colors.RESET} ({len(data['issues'])}/{len(data['comments'])})")
    
    # Get unique contributors
    unique_contributors = set().union(*[set(contribs) for contribs in data['contributors'].values()])
    contributor_count = len(unique_contributors)
    first_10_contributors = sorted(list(unique_contributors))[:10]
    contributor_list = ', '.join(first_10_contributors)
    if contributor_count > 10:
        contributor_list += ' <cut+10>'
    print(f"{Colors.BLUE}Unique Contributors:{Colors.RESET} {contributor_count} [{contributor_list}]")

    # Print email and name associations
    email_groups = {}
    
    # Collect emails from identity_rotation
    if data.get('identity_rotation', {}).get('multiple_names_per_email'):
        for email, info in data['identity_rotation']['multiple_names_per_email'].items():
            if email not in email_groups:
                email_groups[email] = set()
            email_groups[email].update(info['names'])
    
    # Collect emails from unique_emails
    if data.get('unique_emails') and data['unique_emails'][0]:
        # Print owner emails
        if data['unique_emails'][0].get('owner'):
            print(f"\n{Colors.BLUE}Emails owner:{Colors.RESET}")
            owner_emails = {}
            for entry in data['unique_emails'][0]['owner']:
                email = entry['email']
                name = entry['name']
                if email not in owner_emails:
                    owner_emails[email] = set()
                owner_emails[email].add(name)
            for email, names in sorted(owner_emails.items()):
                if email:  # Skip empty emails
                    print(f"- {email}: {', '.join(sorted(names))}")
        
        # Print contributor emails
        if data['unique_emails'][0].get('contributors'):
            print(f"\n{Colors.BLUE}Emails contributors:{Colors.RESET}")
            contributor_emails = {}
            for entry in data['unique_emails'][0]['contributors']:
                email = entry['email']
                name = entry['name']
                if email not in contributor_emails:
                    contributor_emails[email] = set()
                contributor_emails[email].add(name)
            for email, names in sorted(contributor_emails.items()):
                if email:  # Skip empty emails
                    print(f"- {email}: {', '.join(sorted(names))}")
        
        # Print other emails
        if data['unique_emails'][0].get('other'):
            print(f"\n{Colors.BLUE}Emails other:{Colors.RESET}")
            other_emails = {}
            for entry in data['unique_emails'][0]['other']:
                email = entry['email']
                name = entry['name']
                if email not in other_emails:
                    other_emails[email] = set()
                other_emails[email].add(name)
            for email, names in sorted(other_emails.items()):
                if email:  # Skip empty emails
                    print(f"- {email}: {', '.join(sorted(names))}")
    
    # Print PRs to other repos
    if data.get('pull_requests_to_other_repos'):
        print(f"\n{Colors.BLUE}PRs to:{Colors.RESET}")
        for repo, pr_numbers in data['pull_requests_to_other_repos'].items():
            print(f"{repo}: {len(pr_numbers)}")
    
    if "potential_copy" in data and data["potential_copy"]:
        print(f"\n{Colors.RED}WARNING: Profile contains {len(data['potential_copy'])} potentially copied repositories{Colors.RESET}")

    if "commit_filter" in data and data["commit_filter"]:
        for obj in data["commit_filter"]:
            if obj["search_results"] < 10:
                print(
                    f"{Colors.YELLOW}INFO: Unique commit message found in:{Colors.RESET} {data['profile_info']['login']}/{obj['target_repo']} {Colors.YELLOW}message:{Colors.RESET} {obj['target_commit']} "
                )


def parse_report(username, key=None, summary=False, out_path=None):
    """Parse and display data from report.json"""
    data_manager = DataManager(username, out_path)
    report_path = data_manager.report_file

    if not os.path.exists(report_path):
        logging.error(f"No report found for {username} at {report_path}")
        return False

    try:
        with open(report_path, "r") as f:
            data = json.load(f)

        if summary:
            print(f"\n{Colors.GREEN}Summary for: { Colors.RESET}{username}")
            print_summary(data)
            return True

        if key:
            value = get_nested_value(data, key)
            if value is not None:
                formatted_value = format_value(value, indent=1)
                print(f"\n{key}:")
                print(formatted_value)
                return True
            else:
                logging.error(f"Key '{key}' not found in report data")
                return False

        # If no specific key requested, pretty print entire report
        print(json.dumps(data, indent=2))
        return True

    except json.JSONDecodeError:
        logging.error(f"Invalid JSON in report file: {report_path}")
        return False
    except Exception as e:
        logging.error(f"Error parsing report: {str(e)}")
        return False
