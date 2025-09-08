# GitHub Profile Analyzer

A powerful OSINT tool for analyzing GitHub profiles and detecting suspicious activity patterns. This tool helps identify potential bot accounts, scammers, and fake developer profiles by analyzing various aspects of GitHub activity.

## Features

- **Profile Analysis**: Download and analyze complete GitHub profile data
- **Commit Analysis**: Detect copied commits and suspicious commit patterns
- **Identity Detection**: Track email/name variations and potential identity rotation
- **Organization Scanning**: Analyze contributors across entire organizations
- **Activity Monitoring**: Real-time monitoring of profile changes and activities
- **Advanced Tools**: 
  - Commit author lookup
  - Activity checking
  - Search result dumping
  - Organization scanning

## Installation

```sh
pip install gh-fake-analyzer
```

### Requirements
- Python 3.7 or higher
- Git installed on your system (`sudo apt install git`)

### GitHub Token Setup
You need a GitHub API token for full functionality. Set it up in one of these ways:
1. Create a `.env` file with `GH_TOKEN=<your_token>`
2. Use `--token <your_token>` flag when running commands
3. Set environment variable: `export GH_TOKEN=<your_token>`

### Local Installation

#### Option 1: Clone and Install
```sh
# Clone the repository
git clone https://github.com/shortdoom/gh-fake-analyzer.git
cd gh-fake-analyzer

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package in development mode
pip install -e .
```

#### Option 2: Install Dependencies Manually
```sh
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install requests==2.32.3
pip install python-dotenv==1.0.1
pip install python-dateutil==2.9.0.post0
pip install GitPython==3.1.43
pip install urllib3==2.2.2

# Clone the repository
git clone --filter=blob:none --sparse https://github.com/shortdoom/gh-fake-analyzer.git
cd gh-fake-analyzer
git sparse-checkout set --no-cone '*' '!profiles'

# Add the package to Python path
export PYTHONPATH=$PYTHONPATH:$(pwd)/src  # On Windows: set PYTHONPATH=%PYTHONPATH%;%CD%\src
```

#### Configuration for Development
1. Create a local `config.ini` file in your working directory:
```ini
[LIMITS]
MAX_FOLLOWING = 1000
MAX_FOLLOWERS = 1000
MAX_REPOSITORIES = 1000
CLONE_DEPTH = 100
CLONE_BARE = True
MONITOR_SLEEP = 10
REMOVE_REPO = True
```

2. Set up your GitHub token in `.env`:
```sh
echo "GH_TOKEN=your_token_here" > .env
```

3. Test the installation:
```sh
gh-analyze --help
```

## Usage

### Quick Start Recipe

The most common flow for using the `gh-fake-analyzer` in CTI related tasks is to:

```sh

gh-analyze <username>

# or

gh-analyze --targets <path/to/newlinefile/targets>

# then, for a quick view

gh-analyze --parse <username> --summary

# other often used command is to extract full contributors information from organizations

gh-analyze --tool scan_organization --scan-org <org_name>

# optionally, append --full-analysis to immediately perform full scan on each contributor

gh-analyze --tool scan_organization --scan-org <org_name> --full-analysis

```

It is a good practice to create `targets/` folder in the directory you are running `gh-analyze` from. In there you can build your own list of `targets` to scan as well as create `connections_filter/usernames` file for `activity_check` and `scan_repository` tools.

`github_cache.sqlite` file will be created on the first run to speed up potential re-downloading from the same endpoints. Feel free to remove it as needed.

## All Commands

### Basic Profile Analysis

```sh
# Analyze a single user
gh-analyze <username>

# Analyze multiple users from a file (one username per line)
gh-analyze --targets <file>

# Custom output directory
gh-analyze <username> --out_path /path/to/dir

# Include forked repositories in analysis (default: off)
gh-analyze <username> --forks

# Only fetch basic profile data (no commits, followers, etc.)
gh-analyze <username> --only_profile

# Regenerate report from existing data without fetching from GitHub
gh-analyze <username> --regenerate
```

### Advanced Analysis
```sh
# Search for copied commits in a specific repository
gh-analyze <username> --commit_search <repo_name>

# Search for copied commits across all repositories
gh-analyze <username> --commit_search

# Monitor user activity in real-time
gh-analyze <username> --monitor

# Monitor multiple users from a file
gh-analyze --targets <file> --monitor

# Parse and display specific data from an existing report (<username> needs to be in the default out/ directory, otherwise - supply full path)
gh-analyze --parse <username> --key <output_key>

# Display summary of profile (<username> needs to be in the default out/ directory, otherwise - supply full path)
gh-analyze --parse <username> --summary

# Quick-dump specific data to a file
gh-analyze --parse <username> --key unique_emails >> dump.txt
```

### Organization Analysis
```sh
# Scan a single organization
gh-analyze --tool scan_organization --scan-org <org_name>

# Scan multiple organizations from a file
gh-analyze --tool scan_organization --org-targets <file>

# Perform full analysis for each contributor (generates report.json file for each contributor)
gh-analyze --tool scan_organization --scan-org <org_name> --full-analysis
```

### Advanced Tools
```sh
# Get detailed commit author information
gh-analyze --tool get_commit_author --commit-author <sha>

# Search GitHub users
gh-analyze --tool dump_search_results --search "<query>" --endpoint users

# Search GitHub code
gh-analyze --tool dump_search_results --search "<query>" --endpoint code

# Check activity patterns of multiple users, requires targets/connections_filter/usernames file with list of target usernames to check activity against
gh-analyze --tool check_activity --targets <file>

# Find interesting files in user's repositories (.txt, .pdf, binary files etc.)
gh-analyze --tool find_interesting_files <username>

# Find interesting files for multiple users from a file (.txt, .pdf, binary files etc.)
gh-analyze --tool find_interesting_files --targets <file>

# Custom output directory
gh-analyze --tool find_interesting_files <username> --out_path /path/to/dir

# Disable logging to script.log
gh-analyze --logoff
```

## Configuration

The tool uses a configuration file at `~/.gh_fake_analyzer/config.ini`. You can create a local `config.ini` to override settings:

```ini
[LIMITS]
MAX_FOLLOWING = 1000
MAX_FOLLOWERS = 1000
MAX_REPOSITORIES = 1000
CLONE_DEPTH = 100
CLONE_BARE = True
MONITOR_SLEEP = 10
REMOVE_REPO = True
```

## Output

Analysis results are saved in the `out` directory with the following structure:

### report.json Structure

The `report.json` file contains comprehensive data about the analyzed GitHub profile:

#### Profile Information
- `profile_info`: Basic GitHub user profile data
  - `login`: GitHub username
  - `name`: Display name
  - `location`: User's location
  - `bio`: Profile bio
  - `company`: Company/organization
  - `blog`: Website/blog URL
  - `email`: Public email
  - `created_at`: Account creation date
  - `updated_at`: Last profile update
  - `followers`: Number of followers
  - `following`: Number of following

#### Repository Statistics
- `original_repos_count`: Number of original repositories
- `forked_repos_count`: Number of forked repositories
- `repo_list`: Names of all non-forked repositories
- `forked_repo_list`: Names of all forked repositories
- `repos`: Full repository data for every user repository (includes metadata, languages, stars, etc.)

#### Social Network Analysis
- `mutual_followers`: List of accounts that follow and are followed by the user
- `following`: List of accounts the user follows
- `followers`: List of accounts following the user

#### Contribution Analysis
- `unique_emails`: Emails and associated names extracted from commit data
- `contributors`: User's repositories and their contributors
- `pull_requests_to_other_repos`: List of PRs made to other repositories
- `commits_to_other_repos`: List of commits made to repositories not owned by the user
- `commits`: Full commit data for every user repository
- `issues`: List of issues opened by the user
- `comments`: List of comments made by the user

#### Activity Tracking
- `recent_events`: List of recent events on the analyzed account (last 90 days)
  - Stars
  - Pushes
  - Forks
  - Issues
  - Pull requests
  - Profile updates

#### Error Tracking
- `errors`: List of repositories that failed to retrieve data
  - Network errors
  - DMCA takedowns
  - Access denied
  - Repository not found

#### Suspicious Activity Indicators
- `potential_copy`: List of repositories with first commit date earlier than account creation
- `commit_filter`: List of repositories with similar/duplicated commit messages

### Additional Output Files
- User avatar downloaded to the output directory
- `script.log`: Detailed logging of the analysis process
- `monitoring.log`: Activity monitoring logs (when using --monitor)


## Disclaimer

This tool is for reconnaissance purposes only. The confidence in detecting "malicious" GitHub profiles varies, and many regular user accounts may appear in analysis files. Do not make baseless accusations based on this content. All information is sourced from publicly available third-party sources.