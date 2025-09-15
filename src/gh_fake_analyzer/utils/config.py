import os
import configparser
import logging
from dotenv import load_dotenv
import shutil

DEFAULT_CONFIG = {
    "LIMITS": {
        "MAX_FOLLOWING": "1000",
        "MAX_FOLLOWERS": "1000",
        "MAX_REPOSITORIES": "1000",
        "CLONE_DEPTH": "100",
        "CLONE_BARE": "True",
        "MONITOR_SLEEP": "10",
        "REMOVE_REPO": "True",
    },
}


def load_github_token():
    """
    Load GitHub token with the following precedence:
    1. System environment variable (export GH_TOKEN=xxx)
    2. Local .env file
    """
    # Check system env var first
    token = os.getenv("GH_TOKEN")
    if token:
        return token

    # Try loading from .env file
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        token = os.getenv("GH_TOKEN")
        if token and token.strip() and token != "your_token":
            return token

    return None


def get_config_path():
    """Get the path to the configuration file analyzer is using"""
    user_config = os.path.expanduser("~/.gh_fake_analyzer_config.ini")
    local_config = os.path.join(os.getcwd(), "config.ini")
    package_config = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config.ini"
    )

    for config_path in [local_config, user_config, package_config]:
        if os.path.exists(config_path):
            return config_path

    # Fallback to default config
    config = configparser.ConfigParser()
    config.update(DEFAULT_CONFIG)

    with open(user_config, "w") as f:
        config.write(f)

    return user_config


def setup_logging(log_name="script.log", logoff=False):
    """
    Set up logging configuration for either the main script or monitoring.
    Creates a new logger if monitoring.log, uses root logger for script.log.
    """

    if logoff:
        return

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
CLONE_BARE = config["LIMITS"]["CLONE_BARE"].lower() in ("true", "1", "yes")
MONITOR_SLEEP = int(config["LIMITS"]["MONITOR_SLEEP"])
REMOVE_REPO = config["LIMITS"]["REMOVE_REPO"].lower() in ("true", "1", "yes")


def get_user_data_dir() -> str:
    """Return the directory under the user's home used for analyzer data."""
    return os.path.expanduser("~/.gh_fake_analyzer")


def get_default_target_list_dir() -> str:
    """Compute the default target_list directory path in the user's home."""
    return os.path.join(get_user_data_dir(), "target_list")


def ensure_default_target_list() -> str:
    """
    Ensure the default target_list directory and example files exist under the
    user's data dir. Returns the directory path.
    """
    target_dir = get_default_target_list_dir()
    try:
        os.makedirs(target_dir, exist_ok=True)
        # Create example files if missing
        usernames_path = os.path.join(target_dir, "USERNAMES")
        orgs_path = os.path.join(target_dir, "ORGANIZATIONS")
        if not os.path.exists(usernames_path):
            with open(usernames_path, "w") as f:
                f.write("example_user\n")
        if not os.path.exists(orgs_path):
            with open(orgs_path, "w") as f:
                f.write("example_org\n")
    except Exception as e:
        logging.debug(f"Failed to ensure default target_list directory: {e}")
    return target_dir


def get_package_target_list_dir() -> str:
    """Return the path to the packaged target_list templates inside the package."""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "target_list")


def ensure_local_target_list() -> str:
    """
    Ensure a ./target_list directory exists in the current working directory.
    If missing, copy packaged templates into it. Returns the directory path.
    """
    dest_dir = os.path.join(os.getcwd(), "target_list")
    if os.path.isdir(dest_dir) and os.listdir(dest_dir):
        return dest_dir
    try:
        os.makedirs(dest_dir, exist_ok=True)
        src_dir = get_package_target_list_dir()
        for fname in ("USERNAMES", "ORGANIZATIONS"):
            src = os.path.join(src_dir, fname)
            dst = os.path.join(dest_dir, fname)
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.copyfile(src, dst)
        return dest_dir
    except Exception as e:
        logging.debug(f"Failed to prepare local ./target_list: {e}")
        return dest_dir
