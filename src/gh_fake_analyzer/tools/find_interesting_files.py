import logging
import re
import json
from typing import List, Dict, Set, Optional, Union
from ..utils.api import APIUtils
import os
import csv
from datetime import datetime

class FilePattern:
    """Class to define file patterns to search for"""
    def __init__(self, pattern: str, description: str):
        self.pattern = pattern
        self.description = description

class FileSearcher:
    """Class to search for files in GitHub repositories"""
    def __init__(self, api_utils: APIUtils):
        self.api_utils = api_utils
        self.default_patterns = [
            FilePattern(r'\.zip$', 'ZIP archive'),
            FilePattern(r'\.rar$', 'RAR archive'),
            FilePattern(r'\.pdf$', 'PDF document'),
            FilePattern(r'\.txt$', 'Text file'),
            FilePattern(r'\.sql$', 'SQL file'),
        ]
        
    def _parse_response(self, response: Union[str, dict, list]) -> Union[dict, list]:
        """Parse API response into proper format"""
        logging.debug(f"Parsing response of type: {type(response)}")
        if isinstance(response, (dict, list)):
            logging.debug(f"Response is already dict/list: {str(response)[:200]}...")
            return response
        if isinstance(response, str):
            logging.debug(f"Attempting to parse string response: {response[:200]}...")
            try:
                # Check if it's an error message
                if response.startswith('{') and '"message"' in response:
                    error_data = json.loads(response)
                    logging.error(f"GitHub API error: {error_data.get('message', 'Unknown error')}")
                    return {}
                parsed = json.loads(response)
                logging.debug(f"Successfully parsed JSON response: {str(parsed)[:200]}...")
                return parsed
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse response as JSON: {str(e)}")
                logging.error(f"Response content: {response[:200]}...")
                return {}
        
    def get_repository_files(self, owner: str, repo: str, path: str = '') -> List[Dict]:
        """
        Get all files in a repository using GitHub API tree endpoint
        
        Args:
            owner (str): Repository owner
            repo (str): Repository name
            path (str): Path to start search from (default: root)
            
        Returns:
            List[Dict]: List of file information dictionaries
        """
        branch_names = ['main', 'master', 'dev', 'develop', 'development']
        for branch in branch_names:
            try:
                url = f"{self.api_utils.GITHUB_API_URL}/repos/{owner}/{repo}/git/trees/{branch}"
                if path:
                    url += f"?recursive=1"
                logging.debug(f"Trying to fetch tree from: {url}")
                
                # Use requests directly to get status code and content
                import requests
                headers = self.api_utils.HEADERS.copy()
                response = requests.get(url, headers=headers)
                logging.debug(f"Tree endpoint status code: {response.status_code}")
                if response.status_code == 404:
                    logging.info(f"Branch '{branch}' not found for {owner}/{repo}, trying next branch.")
                    continue
                if response.status_code == 422:
                    logging.info(f"Unprocessable Entity (422) for {owner}/{repo} on branch '{branch}'. Repo may be empty or branch missing. Skipping.")
                    continue
                if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers and response.headers['X-RateLimit-Remaining'] == '0':
                    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                    import time
                    wait_for = max(1, reset_time - int(time.time()))
                    logging.warning(f"Rate limit exceeded. Waiting {wait_for} seconds.")
                    time.sleep(wait_for)
                    continue
                if response.status_code != 200:
                    logging.warning(f"Unexpected status code {response.status_code} for {owner}/{repo} on branch '{branch}'. Skipping.")
                    continue
                
                tree_response = response.json()
                if not isinstance(tree_response, dict):
                    logging.debug(f"Invalid tree response format for {owner}/{repo} using branch {branch}: {type(tree_response)}")
                    continue
                if 'message' in tree_response:
                    logging.info(f"GitHub API error for {owner}/{repo} using branch {branch}: {tree_response['message']}")
                    continue
                if 'tree' not in tree_response:
                    logging.debug(f"No tree data in response for {owner}/{repo} using branch {branch}")
                    continue
                if tree_response.get('truncated'):
                    logging.warning(f"Tree for {owner}/{repo} on branch '{branch}' is truncated. Not all files will be listed.")
                tree_data = tree_response['tree']
                if not isinstance(tree_data, list):
                    logging.debug(f"Tree data is not a list for {owner}/{repo} using branch {branch}")
                    continue
                logging.info(f"Successfully fetched tree from branch {branch} for {owner}/{repo}")
                logging.debug(f"Found {len(tree_data)} items in tree")
                return tree_data
            except Exception as e:
                logging.debug(f"Error fetching repository tree for {owner}/{repo} using branch {branch}: {str(e)}")
                continue
        logging.error(f"Could not fetch tree for {owner}/{repo} using any of the branches: {', '.join(branch_names)}")
        return []

    def find_matching_files(self, 
                          owner: str, 
                          repo: str, 
                          patterns: Optional[List[FilePattern]] = None,
                          max_depth: Optional[int] = None) -> Dict[str, List[Dict]]:
        """
        Find files matching specified patterns in a repository
        
        Args:
            owner (str): Repository owner
            repo (str): Repository name
            patterns (List[FilePattern], optional): List of patterns to search for
            max_depth (int, optional): Maximum directory depth to search
            
        Returns:
            Dict[str, List[Dict]]: Dictionary mapping pattern descriptions to matching files
        """
        if patterns is None:
            patterns = self.default_patterns
        
        # List of filenames to ignore (case-insensitive)
        ignore_files = {
            'requirements.txt', 'requirements-dev.txt', 'license.txt', 'readme.txt', 'changelog.txt',
            'contributing.txt', 'notice.txt', 'authors.txt', 'code_of_conduct.txt',
            'security.txt', 'license', 'readme', 'LICENSE',
            '.gitignore', '.ds_store', '.prettierrc', '.prettierignore', 'Gemfile', '.babelrc1',
            '.gitmodules', '.gitattributes', '.editorconfig', '.dockerignore', '.babelrc', '.buckconfig',
            '.flowconfig', '.watchmanconfig', '.npmrc', '.nvmrc', '.ruby-version', '.firebaserc',
            '.browserslistrc', '.npmignore', '.eslintignore', '.solhintignore', 'Makefile', 'Procfile',
            'artisan', 'Rakefile', 'Guardfile', '.eslintcache', 'Dockerfile', '.eslintrc',
            '.htaccess', 'robots.txt', 'remappings.txt', 'gradlew', 'CODEOWNERS', 'CNAME',
            }
        
        # Add a new category for files without an extension
        no_ext_category = 'No Extension (potential binary/text file)'
        matching_files = {pattern.description: [] for pattern in patterns}
        matching_files[no_ext_category] = []
        files = self.get_repository_files(owner, repo)
        
        if not files:
            return matching_files
            
        logging.debug(f"Processing {len(files)} files in repository {owner}/{repo}")
        
        for file_info in files:
            if not isinstance(file_info, dict):
                logging.debug(f"Skipping non-dict file info: {type(file_info)}")
                continue
                
            if file_info.get('type') != 'blob':  # Skip directories
                logging.debug(f"Skipping non-blob type: {file_info.get('type')}")
                continue
                
            path = file_info.get('path', '')
            if not path:
                logging.debug("Skipping file with no path")
                continue
                
            # Check ignore list (case-insensitive, basename only)
            import os
            basename = os.path.basename(path).lower()
            if basename in ignore_files:
                logging.debug(f"Ignoring file due to ignore list: {basename}")
                continue
                
            # Check for files without an extension
            root, ext = os.path.splitext(basename)
            if not ext:
                logging.debug(f"Found file without extension: {path}")
                matching_files[no_ext_category].append({
                    'path': path,
                    'sha': file_info.get('sha', ''),
                    'size': file_info.get('size', 0),
                    'url': file_info.get('url', '')
                })
                # Continue to next file (do not double count in patterns)
                continue
                
            if max_depth is not None:
                depth = path.count('/')
                if depth > max_depth:
                    logging.debug(f"Skipping file at depth {depth} > {max_depth}: {path}")
                    continue
            
            for pattern in patterns:
                if re.search(pattern.pattern, path, re.IGNORECASE):
                    logging.debug(f"Found matching file: {path} for pattern {pattern.pattern}")
                    matching_files[pattern.description].append({
                        'path': path,
                        'sha': file_info.get('sha', ''),
                        'size': file_info.get('size', 0),
                        'url': file_info.get('url', '')
                    })
                    
        return matching_files

def find_interesting_files(targets: List[str], out_path: Optional[str] = None) -> None:
    """
    Find interesting files in all non-forked repositories of users
    
    Args:
        targets (List[str]): List of GitHub usernames to analyze
        out_path (str, optional): Custom output directory path
    """
    try:
        api_utils = APIUtils()
        searcher = FileSearcher(api_utils)
        
        # Create timestamped output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(out_path or "out", f"TOOL_FILE_SCAN_{timestamp}")
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, "interesting_files.csv")

        # Initialize CSV file with headers
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['username', 'repository', 'files', 'size'])

        for username in targets:
            logging.info(f"Searching interesting files for user: {username}")
            
            # Get user's repositories
            repos_url = f"{api_utils.GITHUB_API_URL}/users/{username}/repos"
            logging.debug(f"Fetching repositories from: {repos_url}")
            repos_list = api_utils.fetch_all_pages(repos_url)
            
            if not repos_list:
                logging.error(f"No repositories found for user {username}")
                continue
                
            # Filter out forked repositories and empty repositories
            non_forked_repos = [
                repo for repo in repos_list 
                if isinstance(repo, dict) and
                not repo.get('fork', True) and 
                repo.get('size', 0) > 0 and 
                not repo.get('archived', False)
            ]
            
            if not non_forked_repos:
                logging.info(f"No non-forked repositories found for user {username}")
                continue
                
            for repo in non_forked_repos:
                repo_name = repo.get('name', '')
                if not repo_name:
                    continue
                    
                logging.info(f"Searching files in repository: {repo_name}")
                matching_files = searcher.find_matching_files(username, repo_name)
                
                if any(matching_files.values()):
                    # Write results to CSV
                    with open(output_file, 'a', newline='') as f:
                        writer = csv.writer(f)
                        for file_type, file_list in matching_files.items():
                            if file_list:
                                for file in file_list:
                                    writer.writerow([
                                        username,
                                        repo_name,
                                        file['path'],
                                        file['size']
                                    ])
                    logging.info(f"Found interesting files in {repo_name}")
                    
        logging.info(f"Results saved to {output_file}")
            
    except Exception as e:
        logging.error(f"Error in find_interesting_files: {str(e)}")
        logging.exception("Full traceback:")
