import argparse
import time
import logging
from .modules.output import parse_report
from .modules.analyze import GitHubProfileAnalyzer
from .modules.monitor import GitHubMonitor
from .utils.api import APIUtils
from .modules.output import Colors
from .utils.config import setup_logging, get_config_path, load_github_token
from .tools.dump_search_results import dump_search_results
from .tools.get_commit_author import get_commit_author
from .tools.check_activity import check_activity
from .tools.scan_organization import scan_organization, scan_organizations
from .tools.scan_repository import scan_repositories
from .tools.find_interesting_files import find_interesting_files
from .tools.get_external_prs import get_external_prs

def read_targets(file_path):
    """Reads a list of GitHub usernames from a file."""
    try:
        with open(file_path, "r") as file:
            targets = file.read().splitlines()
        if targets:
            logging.info(f"Targets read from {file_path}")
        return targets
    except Exception as e:
        logging.error(f"Error reading targets file {file_path}: {e}")
        return []


def process_target(username, commit_search=None, only_profile=False, out_path=None, regenerate=False):
    try:
        analyzer = GitHubProfileAnalyzer(username, out_path=out_path)

        if regenerate:
            if analyzer.data:  # Only regenerate if we have existing data
                logging.info(f"Regenerating report for {username} from existing data...")
                analyzer.generate_report()
                return
            else:
                logging.error(f"No existing data found for {username}. Cannot regenerate report.")
                return

        if only_profile:
            logging.info(f"Only fetching profile data for {username}...")
            analyzer.fetch_profile_data()
            analyzer.data_manager.save_output(analyzer.data)
            return

        if commit_search:
            logging.info(
                f"Searching for copied commits {'in ' + commit_search if isinstance(commit_search, str) else 'across all repos'}..."
            )

            if analyzer.data:
                logging.info(f"Profile data exists. Running filter commit search.")
                analyzer.filter_commit_search(
                    repo_name=commit_search if isinstance(commit_search, str) else None
                )
                return
            else:
                logging.info(
                    f"Profile data not found. Running analysis before commit search."
                )
                analyzer.run_analysis()
                logging.info(f"Analysis done. Running filter commit search.")
                analyzer.filter_commit_search(
                    repo_name=commit_search if isinstance(commit_search, str) else None
                )
                logging.info(f"Generating report for {username}...")
                analyzer.generate_report()
                logging.info(f"Processing completed for {username}")
                return
        else:
            logging.info(f"Starting full analysis for {username}...")
            analyzer.run_analysis()

            logging.info(f"Generating report for {username}...")
            analyzer.generate_report()

            logging.info(f"Processing completed for {username}")
            return

    except Exception as e:
        logging.error(f"Error processing target {username}: {e}")


def terminal():
    parser = argparse.ArgumentParser(
        description="Dump and analyze GitHub profiles. Focused on detecting fake developers, phishing, bot-networks and scammers."
    )
    parser.add_argument(
        "username",
        type=str,
        nargs="?",
        help="GitHub username to analyze",
    )
    parser.add_argument(
        "--targets",
        nargs="?",
        const="targets",
        help="File containing a list of GitHub usernames to analyze",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Activate monitoring (event watcher) for the target or list of targets",
    )
    parser.add_argument(
        "--only_profile",
        action="store_true",
        help="Only fetch profile data (no commits, followers, etc.)",
    )
    parser.add_argument(
        "--commit_search",
        nargs="?",
        const=True,
        metavar="REPO_NAME",
        help="Query GitHub API search for similar commits. Optionally specify a repository name to analyze only that repository.",
    )
    parser.add_argument(
        "--token", help="Optional GitHub API token overriding set env variable"
    )
    parser.add_argument(
        "--out_path",
        type=str,
        nargs="?",
        help="Output directory for analysis results",
    )
    parser.add_argument(
        "--parse",
        type=str,
        metavar="USERNAME",
        help="Parse and display data from an existing report.json file",
    )
    parser.add_argument(
        "--key",
        type=str,
        help="Specific key to retrieve from report.json (supports dot notation for nested keys)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Display summary of key profile information",
    )
    parser.add_argument(
        "--logoff",
        action="store_true",
        help="Disable logging to script.log. Off by default.",
    )
    parser.add_argument(
        "--tool",
        type=str,
        help="Start a specific tool (e.g., dump_search_results)",
    )
    parser.add_argument(
        "--search",
        type=str,
        help="Search query string or GitHub search URL for dump_search_results tool",
    )
    parser.add_argument(
        "--search-terms-file",
        type=str,
        help="File containing multiple search terms (one per line) for dump_search_results tool",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        choices=["users", "code", "issues", "repositories", "commits"],
        default=None,
        help="Specify the search endpoint type for dump_search_results tool. Omit to search across all endpoints.",
    )
    parser.add_argument(
        "--commit-author",
        type=str,
        metavar="SHA",
        help="Get author information for a specific commit SHA using get_commit_author tool",
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Regenerate report from existing data without fetching from GitHub",
    )
    parser.add_argument(
        "--scan-org",
        type=str,
        help="Scan a GitHub organization to collect and analyze contributors (must be used with --tool scan_organization)",
    )
    parser.add_argument(
        "--org-targets",
        type=str,
        help="File containing a list of GitHub organizations to scan (must be used with --tool scan_organization)",
    )
    parser.add_argument(
        "--full-analysis",
        action="store_true",
        help="Perform full analysis (generate_report) for each contributor when scanning organizations",
    )
    parser.add_argument(
        "--forks",
        action="store_true",
        help="Include contributors from forked repositories when scanning organizations",
    )
    parser.add_argument(
        "--scan-repo",
        type=str,
        help="Scan a single GitHub repository to analyze contributors (must be used with --tool scan_repository)",
    )
    parser.add_argument(
        "--repo-targets",
        type=str,
        help="File containing a list of GitHub repositories to scan (must be used with --tool scan_repository)",
    )
    parser.add_argument(
        "--find-files",
        action="store_true",
        help="Search for interesting files in user's repositories",
    )
    parser.add_argument(
        "--external-prs-username",
        type=str,
        help="GitHub username to fetch external PRs for (used with --tool get_external_prs)",
    )
    parser.add_argument(
        "--external-prs-targets",
        type=str,
        help="File containing a list of GitHub usernames to fetch external PRs for (used with --tool get_external_prs)",
    )
    
    args = parser.parse_args()
    start_time = time.time()
    

    if args.logoff:
        print("Logging disabled. You will only see error messages.")
        setup_logging("script.log", True)
    else:
        setup_logging("script.log")
        
        
    if args.parse:
        if parse_report(args.parse, args.key, args.summary, args.out_path):
            return
        else:
            return

    if args.token:
        APIUtils.set_token(args.token)
        logging.info(
            f"{Colors.GREEN}Using Github Token from command line argument{Colors.RESET}"
        )
    else:
        token = load_github_token()
        if token:
            APIUtils.set_token(token)
            logging.info(
                f"{Colors.GREEN}Using Github Token from environment{Colors.RESET}"
            )
        else:
            logging.warning(
                f"{Colors.RED}No GitHub token provided. Rate limits may apply.{Colors.RESET}"
            )

    if args.tool:
        if args.tool == "dump_search_results":
            if not args.search and not args.search_terms_file:
                logging.error("Either --search or --search-terms-file argument is required for dump_search_results tool")
                return
            try:
                dump_search_results(args.search, args.endpoint, args.search_terms_file)
                return
            except Exception as e:
                logging.error(f"Error running dump_search_results: {e}")
                return
        if args.tool == "get_commit_author":
            if not args.commit_author:
                logging.error("--commit-author SHA argument is required for get_commit_author tool")
                return
            try:
                get_commit_author(args.commit_author)
                return
            except Exception as e:
                logging.error(f"Error running get_commit_author: {e}")
                return
        if args.tool == "check_activity":
            if not args.targets:
                logging.error("--targets argument is required for check_activity tool")
                return
            try:
                targets = read_targets(args.targets)
                if not targets:
                    logging.error(f"No targets found in {args.targets}. Exiting.")
                    return
                check_activity(targets)
                return
            except Exception as e:
                logging.error(f"Error running check_activity: {e}")
                return
        if args.tool == "scan_organization":
            if not args.scan_org and not args.org_targets:
                logging.error("--scan-org or --org-targets argument is required for scan_organization tool")
                return
            try:
                if args.scan_org:
                    scan_organization(args.scan_org, args.full_analysis, args.out_path, args.forks)
                elif args.org_targets:
                    org_targets = read_targets(args.org_targets)
                    if not org_targets:
                        logging.error(f"No organizations found in {args.org_targets}. Exiting.")
                        return
                    scan_organizations(org_targets, args.full_analysis, args.out_path, args.forks)
                return
            except Exception as e:
                logging.error(f"Error running scan_organization: {e}")
                return
        if args.tool == "scan_repository":
            if not args.scan_repo and not args.repo_targets:
                logging.error("--scan-repo or --repo-targets argument is required for scan_repository tool")
                return
            try:
                if args.scan_repo:
                    scan_repositories([args.scan_repo], args.out_path)
                elif args.repo_targets:
                    with open(args.repo_targets, 'r') as f:
                        repo_list = [line.strip() for line in f if line.strip()]
                    if not repo_list:
                        logging.error(f"No repositories found in {args.repo_targets}. Exiting.")
                        return
                    scan_repositories(repo_list, args.out_path)
                return
            except Exception as e:
                logging.error(f"Error running scan_repository: {e}")
                return
        if args.tool == "find_interesting_files":
            if not args.username and not args.targets:
                logging.error("Either username or --targets argument is required for find_interesting_files tool")
                return
            try:
                if args.username:
                    find_interesting_files([args.username], args.out_path)
                else:
                    targets = read_targets(args.targets)
                    if not targets:
                        logging.error(f"No targets found in {args.targets}. Exiting.")
                        return
                    find_interesting_files(targets, args.out_path)
                return
            except Exception as e:
                logging.error(f"Error running find_interesting_files: {e}")
                return
        if args.tool == "get_external_prs":
            if not args.external_prs_username and not args.external_prs_targets:
                logging.error("Either --external-prs-username or --external-prs-targets argument is required for get_external_prs tool")
                return
            try:
                if args.external_prs_username:
                    get_external_prs(args.external_prs_username, args.out_path)
                else:
                    usernames = read_targets(args.external_prs_targets)
                    if not usernames:
                        logging.error(f"No usernames found in {args.external_prs_targets}. Exiting.")
                        return
                    get_external_prs(usernames, args.out_path)
                return
            except Exception as e:
                logging.error(f"Error running get_external_prs: {e}")
                return
        else:
            logging.error(f"Tool '{args.tool}' not found.")
            return

    if args.monitor:
        monitor = GitHubMonitor(APIUtils)

        if args.username:
            monitor.monitor([args.username])

        if args.targets:
            targets = read_targets(args.targets)
            if not targets:
                logging.error(f"No targets found in {targets_file}. Exiting.")
                return
            monitor.monitor(targets)

    if args.only_profile:
        logging.info(f"Only fetching profile data for {args.username}...")
        process_target(args.username, only_profile=True, out_path=args.out_path, regenerate=args.regenerate)
        return

    if args.username:
        with open(get_config_path(), 'r') as file:
            logging.info(f"Config: \n{file.read()}")
        logging.info(f"Processing single target: {args.username}")
        
        process_target(args.username, args.commit_search, out_path=args.out_path, regenerate=args.regenerate)

    if args.targets:
        targets_file = args.targets
        
        with open(get_config_path(), 'r') as file:
            logging.info(f"Config: \n{file.read()}")
        logging.info(f"Processing targets from file: {targets_file}")

        targets = read_targets(targets_file)
        if not targets:
            logging.error(f"No targets found in {targets_file}. Exiting.")
            return

        for target in targets:
            logging.info(f"Processing target: {target}")
            process_target(target, args.commit_search, out_path=args.out_path, regenerate=args.regenerate)

    if not args.username and not args.targets:
        logging.error(f"{Colors.RED}No targets specified. Exiting.{Colors.RESET}")
        logging.info(
            "No targets specified. Please provide a valid username or targets file."
        )
        logging.info("Print help with -h or --help.")

    end_time = time.time()
    logging.info(f"Processing completed in {end_time - start_time:.2f} seconds.")


def start_terminal():
    terminal()
