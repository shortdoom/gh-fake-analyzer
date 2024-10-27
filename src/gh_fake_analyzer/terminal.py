import argparse
import time
import logging
from .modules.output import parse_report
from .modules.analyze import GitHubProfileAnalyzer
from .modules.monitor import GitHubMonitor
from .utils.api import APIUtils
from .modules.output import Colors
from .utils.config import setup_logging, get_config_path, load_github_token


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


def process_target(username, commit_search=None, only_profile=False, out_path=None):
    try:
        analyzer = GitHubProfileAnalyzer(username, out_path=out_path)

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
        process_target(args.username, only_profile=True, out_path=args.out_path)
        return

    if args.username:
        with open(get_config_path(), 'r') as file:
            logging.info(f"Config: \n{file.read()}")
        logging.info(f"Processing single target: {args.username}")
        
        process_target(args.username, args.commit_search, out_path=args.out_path)

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
            process_target(target, args.commit_search, out_path=args.out_path)

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
