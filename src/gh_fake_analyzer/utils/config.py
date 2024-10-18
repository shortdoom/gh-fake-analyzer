import os
import configparser
import logging

# Get the path to the configuration file analyzer is using
def get_config_path():
    # Default configuration file in the user's home directory
    user_config = os.path.expanduser("~/.gh_fake_analyzer_config.ini")
    # Optional local configuration file in the current working directory
    local_config = os.path.join(os.getcwd(), "config.ini")
    return local_config if os.path.exists(local_config) else user_config

def setup_logging():
    log_path = os.path.join(os.getcwd(), "script.log")
    logging.basicConfig(
        filename=log_path,
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

# Get paths for configuration and log files
config_path = get_config_path()

# Load configuration
config = configparser.ConfigParser()
config.read(config_path)

# Set limits for the script
MAX_FOLLOWING = int(config["LIMITS"]["MAX_FOLLOWING"])
MAX_FOLLOWERS = int(config["LIMITS"]["MAX_FOLLOWERS"])
MAX_REPOSITORIES = int(config["LIMITS"]["MAX_REPOSITORIES"])
CLONE_DEPTH = int(config["LIMITS"]["CLONE_DEPTH"])

