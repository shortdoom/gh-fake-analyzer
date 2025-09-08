import os
import time
import json
import logging
from datetime import datetime
from ..utils.api import APIUtils
from ..utils.data import DataManager
from ..modules.fetch import GithubFetchManager

# A script to dump profile_info from all of the search results from github
# Example usage: user provides a search string, e.g https://github.com/search?q=check+out+my+address+in+scopescan&type=users
# Script takes all pages of results and dumps the profile_info to an out file
# Should utilize the api.py module to fetch the profile_info

def read_search_terms(file_path: str) -> list:
    """Read search terms from a file, one per line."""
    try:
        with open(file_path, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logging.error(f"Error reading search terms file {file_path}: {e}")
        return []

def dump_search_results(search_string: str, endpoint: str = "users", search_terms_file: str = None) -> None:
    """
    Dump search results from GitHub based on the specified endpoint.
    
    Args:
        search_string (str): Search query or GitHub search URL
        endpoint (str): Type of search endpoint to use ("users" or "code")
        search_terms_file (str): Optional path to file containing multiple search terms
    
    Saves data to /out directory under SearchResults_{endpoint}_{timestamp}.json
    """
    # Determine search terms to process
    search_terms = []
    if search_terms_file:
        search_terms = read_search_terms(search_terms_file)
        if not search_terms:
            logging.error("No valid search terms found in file")
            return
    else:
        if "github.com/search" in search_string:
            search_terms = [search_string.split("q=")[1].split("&")[0]]
        else:
            search_terms = [search_string]

    # Create a single output directory for all results with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_path = f"SearchResults_{endpoint}_{timestamp}"
    data_manager = DataManager(base_path)
    api_utils = APIUtils()
    github_fetch = GithubFetchManager(api_utils)
    output_file = os.path.join(data_manager.user_dir, "report.json")

    all_results = []
    for search_term in search_terms:
        try:
            logging.info(f"Processing search term: {search_term}")
            
            # Get search results based on endpoint
            if endpoint == "users":
                search_results = github_fetch.search_users(search_term)
            else:  # code endpoint
                search_results = github_fetch.search_code(search_term)

            if not search_results:
                logging.warning(f"No search results found for term: {search_term}")
                continue

            total_results = len(search_results)
            logging.info(f"Found {total_results} results for term: {search_term}")

            # Process results based on endpoint
            if endpoint == "users":
                for idx, user in enumerate(search_results, 1):
                    try:
                        if idx > 1:  # Don't delay the first request
                            time.sleep(1)  # 1 second delay between requests

                        profile = github_fetch.fetch_profile_data(user['login'])
                        if profile:
                            all_results.append({
                                'search_term': search_term,
                                'profile': profile
                            })
                            logging.info(f"Fetched profile for {user['login']} ({idx}/{total_results})")

                    except Exception as e:
                        logging.error(f"Error fetching profile for {user['login']}: {e}")
                        continue

            else:  # code endpoint
                for result in search_results:
                    try:
                        repo_name = result.get('repository', {}).get('full_name', '')
                        browser_url = result.get('html_url', '')
                        
                        all_results.append({
                            'search_term': search_term,
                            'repository': repo_name,
                            'url': browser_url
                        })
                    except Exception as e:
                        logging.error(f"Error processing search result: {e}")
                        continue

            # Add delay between different search terms
            time.sleep(2)

        except Exception as e:
            logging.error(f"Error processing search term {search_term}: {e}")
            continue

    # Write all results to a single file
    if all_results:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        logging.info(f"Successfully wrote {len(all_results)} total results to {output_file}")
    else:
        logging.warning("No results were found for any search term")