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


def setup_logging(log_name="script.log"):
    """
    Set up logging configuration for either the main script or monitoring.
    Creates a new logger if monitoring.log, uses root logger for script.log.
    """
    log_path = os.path.join(os.getcwd(), log_name)

    if log_name == "monitoring.log":
        # Create a separate logger for monitoring
        logger = logging.getLogger("monitoring")
        logger.setLevel(logging.DEBUG)
        logger.handlers = []  # Clear any existing handlers

        # Create handlers
        file_handler = logging.FileHandler(log_path)
        console_handler = logging.StreamHandler()

        # Set format
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        # Prevent propagation to root logger
        logger.propagate = False
    else:
        # Configure root logger for script.log
        logging.basicConfig(
            filename=log_path,
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s",
            force=True,  # Force reconfiguration
        )

        # Add console handler for script.log
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        console.setFormatter(formatter)
        logging.getLogger("").addHandler(console)


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
CLONE_BARE = bool(config["LIMITS"]["CLONE_BARE"])
MONITOR_SLEEP = int(config["LIMITS"]["MONITOR_SLEEP"])
REMOVE_REPO = bool(config["LIMITS"]["REMOVE_REPO"])