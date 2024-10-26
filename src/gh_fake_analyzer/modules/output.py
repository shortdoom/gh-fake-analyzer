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
    print(f"{Colors.BLUE}URL:{Colors.RESET} {data['profile_info']['html_url']}")
    print(
        f"{Colors.BLUE}Created At:{Colors.RESET} {data['profile_info']['created_at']}"
    )
    print(
        f"{Colors.BLUE}Updated At:{Colors.RESET} {data['profile_info']['updated_at']}"
    )
    print(f"{Colors.BLUE}Followers:{Colors.RESET} {data['profile_info']['followers']}")
    print(f"{Colors.BLUE}Following:{Colors.RESET} {data['profile_info']['following']}")
    print(
        f"{Colors.BLUE}Mutual Following:{Colors.RESET} {len(data['mutual_followers'])}"
    )
    print(f"{Colors.BLUE}Repositories:{Colors.RESET} {data['original_repos_count']}")
    
    print(
        f"{Colors.BLUE}Forked Repositories:{Colors.RESET} {data['forked_repos_count']}"
    )
    print(f"{Colors.BLUE}Pull Requests:{Colors.RESET} {len(data['pull_requests_to_other_repos'])}")
    print(f"{Colors.BLUE}Unique Emails:{Colors.RESET} {len(data['unique_emails'])}")
    print(f"{Colors.BLUE}Issues Opened:{Colors.RESET} {len(data['issues'])}")
    print(f"{Colors.BLUE}Comments Made:{Colors.RESET} {len(data['comments'])}")
    
    if "potential_copy" in data and data["potential_copy"]:
        print(
            f"\n{Colors.RED}WARNING: Profile contains potentially copied repository{Colors.RESET}"
        )

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
