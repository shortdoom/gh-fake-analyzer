import logging
import os
import csv
from datetime import datetime
from typing import List, Dict
from ..utils.api import APIUtils
from ..utils.data import DataManager
from .check_activity import check_activity
from ..modules.analyze import GitHubProfileAnalyzer

# gh-analyze --tool scan_repository --repo-targets targets/TARGETS
# gh-analyze --tool scan_repository --scan-repo "owner/repo"


def scan_repository(repo_full_name: str, out_path: str = None, append_to_file: str = None, full_analysis: bool = False) -> None:
    """
    Scan a GitHub repository to collect contributors and analyze their activity.
    
    Args:
        repo_full_name (str): The full name of the GitHub repository (owner/repo)
        out_path (str, optional): Custom output directory path
        append_to_file (str, optional): Path to CSV file to append results to
        full_analysis (bool, optional): Perform full analysis for each contributor and generate reports
    """
    logging.info(f"Starting scan of repository: {repo_full_name}")
    
    # Initialize API utilities
    api_utils = APIUtils()
    
    # Create timestamped output directory if not appending to existing file
    if not append_to_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(out_path or "out", f"repo_scan_{timestamp}")
        os.makedirs(output_dir, exist_ok=True)
        final_output_file = os.path.join(output_dir, "repository_contributors_analysis.csv")
    else:
        final_output_file = append_to_file
        output_dir = os.path.dirname(append_to_file) or (out_path or "out")
    
    # Split repository name into owner and repo
    owner, repo = repo_full_name.split('/')
    
    # Fetch all contributors for the repository
    logging.info(f"Fetching contributors for repository: {repo_full_name}")
    contributor_logins: List[str] = []
    try:
        contributors = api_utils.fetch_all_pages(
            f"{api_utils.GITHUB_API_URL}/repos/{owner}/{repo}/contributors"
        )
        contributor_logins = [contributor["login"] for contributor in contributors]
        logging.info(f"Found {len(contributor_logins)} contributors in {repo_full_name}")
    except Exception as e:
        logging.error(f"Error fetching contributors for {repo_full_name}: {e}")
        return
    
    # Create a temporary file for the activity check
    activity_output_file = f"{repo_full_name.replace('/', '_')}_activity_check.csv"
    
    # Run check_activity on the list of contributors
    logging.info("Running activity check on contributors")
    activity_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    activity_dir = "TOOL_CHECK_ACTIVITY_" + activity_timestamp
    
    # Run the activity check
    check_activity(contributor_logins, activity_output_file)
    
    # Process the activity check results and add repository information
    try:
        # Get the DataManager's output directory using the timestamp we saved
        data_manager = DataManager(activity_dir)
        source_file = os.path.join(data_manager.user_dir, activity_output_file)
        
        if os.path.exists(source_file):
            # Read the activity check results
            with open(source_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                activity_results = list(reader)
            
            # Add repository information to each result
            for result in activity_results:
                result['repository'] = repo_full_name
            
            # Check PRs for flagged users
            flags_to_check = [
                'suspicious',
                'target_org_member',
                'large_org_member',
                'high_following',
                'high_followers',
                'follows_target_users',
                'has_target_contributors',
                'has_fork_target_contributors'
            ]
            
            for result in activity_results:
                # Check if user has any flags set to true
                has_flag = any(result.get(flag) == 'true' for flag in flags_to_check)
                
                if has_flag:
                    try:
                        # Search for PRs by this user to the repository
                        pr_url = f"{api_utils.GITHUB_API_URL}/search/issues"
                        pr_params = {
                            "q": f"type:pr author:{result['username']} repo:{owner}/{repo}",
                            "per_page": 100  # Maximum per page
                        }
                        prs = api_utils.fetch_all_pages(pr_url, pr_params)
                        result['pr_count'] = len(prs)
                        result['pr_list'] = ','.join([pr['html_url'] for pr in prs])
                        
                        # Add which flags triggered the PR check
                        triggered_flags = [flag for flag in flags_to_check if result.get(flag) == 'true']
                        result['pr_check_triggered_by'] = ','.join(triggered_flags)
                    except Exception as e:
                        logging.error(f"Error fetching PRs for {result['username']}: {e}")
                        result['pr_count'] = 0
                        result['pr_list'] = ''
                        result['pr_check_triggered_by'] = ''
                else:
                    result['pr_count'] = 0
                    result['pr_list'] = ''
                    result['pr_check_triggered_by'] = ''
            
            # Define the desired column order
            fieldnames = [
                'repository',
                'username',
                'suspicious',
                'high_following_count',
                'high_followers_count',
                'target_contributors_list',
                'follows_target_users_list',
                'fork_target_contributors_list',
                'target_orgs',
                'large_orgs',
                # PR-related columns
                'pr_count',
                'pr_list',
                'pr_check_triggered_by',
                # Continue with remaining columns
                'target_org_member',
                'large_org_member',
                'high_following',
                'high_followers',
                'follows_target_users',
                'has_target_contributors',
                'has_fork_target_contributors',
            ]
            
            # Write or append to the final output file
            file_exists = os.path.exists(final_output_file)
            with open(final_output_file, 'a' if file_exists else 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerows(activity_results)
            
            logging.info(f"Results written to {final_output_file}")
            
            # Remove the temporary activity check file and directory
            os.remove(source_file)
            os.rmdir(data_manager.user_dir)
            
        else:
            logging.error(f"Activity check file not found at {source_file}")
    except Exception as e:
        logging.error(f"Error processing activity check results: {e}")
    
    # Optionally perform full analysis for each contributor
    if full_analysis and contributor_logins:
        logging.info("Performing full analysis for each contributor")
        for contributor in contributor_logins:
            try:
                logging.info(f"Analyzing contributor: {contributor}")
                analyzer = GitHubProfileAnalyzer(contributor, out_path=output_dir)
                analyzer.run_analysis()
                analyzer.generate_report()
            except Exception as e:
                logging.error(f"Error analyzing contributor {contributor}: {e}")


def scan_repositories(repo_list: List[str], out_path: str = None, full_analysis: bool = False) -> None:
    """
    Scan multiple GitHub repositories.
    
    Args:
        repo_list (List[str]): List of GitHub repository full names (owner/repo)
        out_path (str, optional): Custom output directory path
        full_analysis (bool, optional): Perform full analysis for each contributor and generate reports
    """
    # Create a single output file for all repositories
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(out_path or "out", f"repo_scan_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    final_output_file = os.path.join(output_dir, "repository_contributors_analysis.csv")
    
    for repo_full_name in repo_list:
        try:
            scan_repository(repo_full_name, out_path, append_to_file=final_output_file, full_analysis=full_analysis)
        except Exception as e:
            logging.error(f"Error scanning repository {repo_full_name}: {e}") 