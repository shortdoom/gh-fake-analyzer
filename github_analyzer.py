import time
import logging
import argparse
from analyzer import GitHubProfileAnalyzer

# Setup logging
logging.basicConfig(
    filename="script.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

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

def process_target(username, commit_search=False):
    """Process an individual GitHub profile."""
    try:
        analyzer = GitHubProfileAnalyzer(username)
        if not analyzer.exists:
            logging.info(f"Analyzing profile data for {username}...")
            analyzer.run_full_analysis()
        else:
            logging.info(f"Profile data for {username} already exists.")

        if commit_search:
            logging.info(f"Searching for copied commits in {username}'s repos...")
            analyzer.filter_commit_search()

        logging.info(f"Generating report for {username}...")
        analyzer.generate_report()
    except Exception as e:
        logging.error(f"Error processing target {username}: {e}")

def main():
    # Argument parsing
    parser = argparse.ArgumentParser(description="Analyze GitHub profiles.")
    parser.add_argument(
        "username", 
        type=str, 
        nargs="?", 
        help="GitHub username to analyze (if omitted, reads from targets file)"
    )
    parser.add_argument(
        "--targets", 
        type=str, 
        help="File containing a list of GitHub usernames to analyze"
    )
    parser.add_argument(
        "--commit_search", 
        action="store_true", 
        help="Query GitHub API search for similar commits"
    )
    
    args = parser.parse_args()

    start_time = time.time()

    if args.username:
        # Process single target
        logging.info(f"Processing single target: {args.username}")
        process_target(args.username, args.commit_search)
    else:
        logging.info("Processing targets from file...")
        print("Processing targets from `targets` file...")
        # Attempt to read targets from the provided file path first
        targets = read_targets(args.targets) if args.targets else []
        
        # Fallback to the default "targets" file if the provided path was empty
        if not targets:
            logging.warning(f"No targets found in {args.targets}. Falling back to 'targets' file.")
            targets = read_targets("targets")
        
        # Fail if no targets are found after both attempts
        if not targets:
            logging.error("No targets found in either provided file or default 'targets' file. Exiting.")
            print("No targets found. Please provide a valid targets file or specify a username.")
            return

        # Process each target
        for target in targets:
            logging.info(f"Processing target: {target}")
            process_target(target, args.commit_search)

    end_time = time.time()
    print(f"Processing completed in {end_time - start_time:.2f} seconds.")
    logging.info(f"Processing completed in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    main()
