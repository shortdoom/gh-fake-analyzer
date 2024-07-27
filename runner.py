import time
import logging
from analyzer import GitHubProfileAnalyzer

logging.basicConfig(
    filename="runner.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

def read_targets(file_path):
    try:
        with open(file_path, "r") as file:
            targets = file.read().splitlines()
        return targets
    except Exception as e:
        logging.error(f"Error reading targets file: {e}")
        return []

def process_target(username):
    try:
        analyzer = GitHubProfileAnalyzer(username)
        if not analyzer.exists:
            logging.info(f"Analyzing profile data for {username}...")
            analyzer.run_full_analysis()
        else:
            logging.info(f"Profile data for {username} already exists.")

        logging.info(f"Generating report for {username}...")
        analyzer.generate_report()
    except Exception as e:
        logging.error(f"Error processing target {username}: {e}")

if __name__ == "__main__":
    targets_file = "targets"
    targets = read_targets(targets_file)
    start_time = time.time()

    for target in targets:
        logging.info(f"Processing target: {target}")
        process_target(target)

    end_time = time.time()
    print(f"All targets processed.{end_time - start_time:.2f} seconds.")
    logging.info(f"All targets processed.{end_time - start_time:.2f} seconds.")