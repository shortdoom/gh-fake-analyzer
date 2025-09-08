# tools/get_commit_author.py
import logging
from ..utils.api import APIUtils
from ..modules.fetch import GithubFetchManager

def get_commit_author(commit_sha: str) -> None:
    """
    Get commit author information for a specific commit SHA.
    Works for both repository commits and PR commits.
    
    Args:
        commit_sha (str): Full commit SHA hash
    """
    try:
        api_utils = APIUtils()
        github_fetch = GithubFetchManager(api_utils)
        
        # Try direct commit fetch from various repositories
        search_results = github_fetch.search_commits(message=commit_sha)
        
        if search_results:
            commit = search_results[0]
            repo_owner = commit["repository"]["owner"]["login"]
            repo_name = commit["repository"]["name"]
            commit_data = github_fetch.fetch_commit_author(repo_owner, repo_name, commit_sha)
            
            if commit_data:
                # Display commit info
                print(f"\nCommit {commit_sha}:")
                print(f"Repository: {repo_owner}/{repo_name}")
                
                # Author info
                author = commit_data.get("author", {})
                print("\nAuthor:")
                print(f"  Username: {author.get('login', 'N/A')}")
                print(f"  User ID: {author.get('id', 'N/A')}")
                
                commit_info = commit_data.get("commit", {})
                author_info = commit_info.get("author", {})
                print(f"  Name: {author_info.get('name', 'N/A')}")
                print(f"  Email: {author_info.get('email', 'N/A')}")
                print(f"  Date: {author_info.get('date', 'N/A')}")
                
                # Committer info (if different from author)
                committer = commit_data.get("committer", {})
                committer_info = commit_info.get("committer", {})
                if committer.get("login") != author.get("login"):
                    print("\nCommitter:")
                    print(f"  Username: {committer.get('login', 'N/A')}")
                    print(f"  User ID: {committer.get('id', 'N/A')}")
                    print(f"  Name: {committer_info.get('name', 'N/A')}")
                    print(f"  Email: {committer_info.get('email', 'N/A')}")
                    print(f"  Date: {committer_info.get('date', 'N/A')}")
                return
                
        # If not found, try searching for the commit in open pull requests
        pr_search_results = github_fetch.search_pull_requests_by_commit(commit_sha)
        
        if pr_search_results:
            # Extract repo info from the first PR that contains this commit
            pr = pr_search_results[0]
            repo_parts = pr["repository_url"].split("/")
            repo_owner = repo_parts[-2]
            repo_name = repo_parts[-1]
            
            commit_data = github_fetch.fetch_commit_author(repo_owner, repo_name, commit_sha)
            if commit_data:
                # Display commit info (same as above)
                print(f"\nCommit {commit_sha}:")
                print(f"Repository: {repo_owner}/{repo_name}")
                print(f"Found in Pull Request: {pr['html_url']}")
                
                # Author info
                author = commit_data.get("author", {})
                print("\nAuthor:")
                print(f"  Username: {author.get('login', 'N/A')}")
                print(f"  User ID: {author.get('id', 'N/A')}")
                
                commit_info = commit_data.get("commit", {})
                author_info = commit_info.get("author", {})
                print(f"  Name: {author_info.get('name', 'N/A')}")
                print(f"  Email: {author_info.get('email', 'N/A')}")
                print(f"  Date: {author_info.get('date', 'N/A')}")
                
                # Committer info (if different from author)
                committer = commit_data.get("committer", {})
                committer_info = commit_info.get("committer", {})
                if committer.get("login") != author.get("login"):
                    print("\nCommitter:")
                    print(f"  Username: {committer.get('login', 'N/A')}")
                    print(f"  User ID: {committer.get('id', 'N/A')}")
                    print(f"  Name: {committer_info.get('name', 'N/A')}")
                    print(f"  Email: {committer_info.get('email', 'N/A')}")
                    print(f"  Date: {committer_info.get('date', 'N/A')}")
                return
                
        logging.error(f"Could not find commit with SHA: {commit_sha}")
            
    except Exception as e:
        logging.error(f"Error in get_commit_author: {e}")
        raise