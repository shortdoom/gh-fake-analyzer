# A script to dump profile_info from all of the search results from github
# Example usage: user provides a search string, e.g https://github.com/search?q=check+out+my+address+in+scopescan&type=users
# Script takes all pages of results and dumps the profile_info to an out file
# Should utilize the api.py module to fetch the profile_info

import os
import time
import json
import logging
from typing import List, Dict
from ..utils.api import APIUtils
from ..utils.data import DataManager
from ..modules.fetch import GithubFetchManager

# TODO: Allow specifying endpoint (repos, commits, users etc.)
def dump_search_results(search_string: str) -> None:
    """
    Dump profile information for all users found in GitHub search results for search string.
    search_string = "Fullstack developer" returns profiles of all users found in the search results.
    Github Search API Limits apply, max 1000 results, refine query below this limit.
    
    Args:
        search_string (str): Search query or GitHub search URL
    
    Saves data to /out directory under SearchResults_{query}.json
    """
    
    if "github.com/search" in search_string:
        query = search_string.split("q=")[1].split("&")[0]
    else:
        query = search_string

    path = "SearchResults_" + query.replace(" ", "+")
    data_manager = DataManager(path)
    api_utils = APIUtils()
    github_fetch = GithubFetchManager(api_utils)
    partial_file = os.path.join(data_manager.user_dir, "report_partial.json")
    output_file = os.path.join(data_manager.user_dir, "report.json")
    
    try:
        # Get search results
        logging.info(f"Fetching search results for query: {search_string}")
        search_results = github_fetch.search_users(search_string)
        
        if not search_results:
            logging.warning("No search results found")
            return
            
        total_users = len(search_results)
        logging.info(f"Found {total_users} users. Fetching their profiles...")
        
        # Fetch profile data for each user with rate limiting
        profile_data = []
        for idx, user in enumerate(search_results, 1):
            username = user['login']
            try:
                # Add a small delay between requests to avoid hitting rate limits
                if idx > 1:  # Don't delay the first request
                    time.sleep(1)  # 1 second delay between requests
                
                profile = github_fetch.fetch_profile_data(username)
                if profile:
                    profile_data.append(profile)
                    logging.info(f"Fetched profile for {username} ({idx}/{total_users})")
                
                # Save intermediate results every 100 profiles
                if idx % 100 == 0:
                    with open(partial_file, 'w', encoding='utf-8') as f:
                        json.dump(profile_data, f, indent=2, ensure_ascii=False)
                    logging.info(f"Saved partial results ({idx}/{total_users} profiles)")
                
            except Exception as e:
                logging.error(f"Error fetching profile for {username}: {e}")
                continue
        
        # Write final results to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)
            
        logging.info(f"Successfully wrote {len(profile_data)} profiles to {output_file}")
        
        # Clean up partial file if it exists
        if os.path.exists(partial_file):
            os.remove(partial_file)
        
    except Exception as e:
        logging.error(f"Error in dump_search_results: {e}")
        # If we have a partial file, keep it in case of error
        if os.path.exists(partial_file):
            logging.info(f"Partial results are available in {partial_file}")
        raise