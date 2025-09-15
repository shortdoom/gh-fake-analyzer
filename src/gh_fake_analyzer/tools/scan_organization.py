import logging
import os
from datetime import datetime
from ..utils.api import APIUtils
from ..utils.data import DataManager
from .check_activity import check_activity
from ..modules.analyze import GitHubProfileAnalyzer

def scan_organization(org_name, full_analysis=False, out_path=None, include_forks=False):
    """
    Scan a GitHub organization to collect contributors and analyze their activity.
    
    Args:
        org_name (str): The name of the GitHub organization to scan.
        full_analysis (bool): Whether to perform a full analysis for each contributor.
        out_path (str, optional): Custom output directory path.
        include_forks (bool): Whether to include contributors from forked repositories. Defaults to False.
    """
    logging.info(f"Starting scan of organization: {org_name}")
    
    # Initialize API utilities
    api_utils = APIUtils()
    
    # Create timestamped output directory for the organization
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    org_dir = os.path.join(out_path or "out", f"{org_name}_{timestamp}")
    os.makedirs(org_dir, exist_ok=True)
    
    # Fetch all repositories in the organization
    logging.info(f"Fetching repositories for organization: {org_name}")
    repos = api_utils.fetch_all_pages(f"{api_utils.GITHUB_API_URL}/orgs/{org_name}/repos")
    logging.info(f"Found {len(repos)} repositories in {org_name}")
    
    # Collect all contributors
    all_contributors = set()
    for repo in repos:
        repo_name = repo["name"]
        # Skip forked repositories unless explicitly included
        if repo["fork"] and not include_forks:
            logging.info(f"Skipping forked repository: {repo_name}")
            continue
            
        logging.info(f"Fetching contributors for repository: {repo_name}")
        try:
            contributors = api_utils.fetch_all_pages(f"{api_utils.GITHUB_API_URL}/repos/{org_name}/{repo_name}/contributors")
            contributor_logins = [contributor["login"] for contributor in contributors]
            all_contributors.update(contributor_logins)
            logging.info(f"Found {len(contributor_logins)} contributors in {repo_name}")
        except Exception as e:
            logging.error(f"Error fetching contributors for {repo_name}: {e}")
    
    # Save the list of contributors
    contributors_file = os.path.join(org_dir, "contributors.txt")
    with open(contributors_file, "w") as f:
        for contributor in sorted(all_contributors):
            f.write(f"{contributor}\n")
    logging.info(f"Saved {len(all_contributors)} contributors to {contributors_file}")
    
    # Run check_activity on the list of contributors
    logging.info("Running activity check on contributors")
    # Create a custom output file name for this organization
    activity_output_file = f"{org_name}_activity_check.csv"
    
    # Get the current timestamp for this activity check
    activity_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    activity_dir = "TOOL_CHECK_ACTIVITY_" + activity_timestamp
    
    # Run the activity check
    check_activity(list(all_contributors), activity_output_file)
    
    # Move the activity check file to the organization directory
    try:
        # Get the DataManager's output directory using the timestamp we saved
        data_manager = DataManager(activity_dir)
        source_file = os.path.join(data_manager.user_dir, activity_output_file)
        target_file = os.path.join(org_dir, activity_output_file)
        
        if os.path.exists(source_file):
            os.rename(source_file, target_file)
            logging.info(f"Moved activity check results to {target_file}")
            
            # Remove the empty activity check directory
            try:
                os.rmdir(data_manager.user_dir)
                logging.info(f"Removed empty activity check directory: {data_manager.user_dir}")
            except Exception as e:
                logging.error(f"Error removing activity check directory: {e}")
        else:
            logging.error(f"Activity check file not found at {source_file}")
    except Exception as e:
        logging.error(f"Error moving activity check file: {e}")
    
    # Optionally perform full analysis for each contributor
    if full_analysis:
        logging.info("Performing full analysis for each contributor")
        for contributor in all_contributors:
            try:
                logging.info(f"Analyzing contributor: {contributor}")
                analyzer = GitHubProfileAnalyzer(contributor, out_path=org_dir)
                analyzer.run_analysis()
                analyzer.generate_report()
            except Exception as e:
                logging.error(f"Error analyzing contributor {contributor}: {e}")
    
    logging.info(f"Completed scan of organization: {org_name}")

def scan_organizations(org_names, full_analysis=False, out_path=None, include_forks=False):
    """
    Scan multiple GitHub organizations.
    
    Args:
        org_names (list): List of GitHub organization names to scan.
        full_analysis (bool): Whether to perform a full analysis for each contributor.
        out_path (str, optional): Custom output directory path.
        include_forks (bool): Whether to include contributors from forked repositories. Defaults to False.
    """
    for org_name in org_names:
        try:
            scan_organization(org_name, full_analysis, out_path, include_forks)
        except Exception as e:
            logging.error(f"Error scanning organization {org_name}: {e}") 