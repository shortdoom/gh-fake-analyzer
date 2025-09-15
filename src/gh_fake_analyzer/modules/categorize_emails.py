import logging
from typing import Dict, List, Any, Set, Tuple


class EmailCategorizer:
    def __init__(self, username: str, contributors_data: List[Dict[str, Any]]):
        self.username = username.lower()

        # Extract all unique contributor usernames across all repos
        try:
            self.all_contributors: Set[str] = set()
            
            # Handle both dictionary and list formats
            if isinstance(contributors_data, dict):
                # If it's a dict like {'repo_name': ['contrib1', 'contrib2']}
                for repo_name, contributors_list in contributors_data.items():
                    if isinstance(contributors_list, list):
                        self.all_contributors.update(contrib.lower() for contrib in contributors_list)
            elif isinstance(contributors_data, list):
                # Original format: list of dicts with 'contributors' key
                for repo_data in contributors_data:
                    if isinstance(repo_data, dict) and "contributors" in repo_data:
                        self.all_contributors.update(
                            contrib.lower() for contrib in repo_data["contributors"]
                        )
            
            # Remove the owner from contributors list
            self.all_contributors.discard(self.username)
                        
        except Exception as e:
            logging.error(f"Error in EmailCategorizer.__init__: {str(e)}")
            logging.error(f"Contributors data: {contributors_data}")
            raise

        # Initialize owner identities and emails
        self.owner_identities: Set[str] = {self.username}
        self.owner_name_email_pairs: Set[Tuple[str, str]] = set()

    def find_all_commits(self, data: Any) -> List[Dict]:
        """Recursively find all commit-like structures in the data."""
        commits = []

        try:
            if isinstance(data, dict):
                # Check if this is a commit with all required fields
                if all(key in data for key in ["sha", "author_name", "author_email", "committer_name", "committer_email"]):
                    commits.append(data)
                # Process nested data
                for key, value in data.items():
                    commits.extend(self.find_all_commits(value))

            elif isinstance(data, list):
                for i, item in enumerate(data):
                    # For list items, we expect them to be commit dictionaries
                    if isinstance(item, dict) and all(key in item for key in ["sha", "author_name", "author_email", "committer_name", "committer_email"]):
                        commits.append(item)
                    else:
                        logging.info(f"DEBUG: Skipping malformed commit data: {str(item)[:200]}")
                
            elif isinstance(data, str):
                logging.info(f"DEBUG: Skipping string data: {data[:100]}...")
                return commits
            
            else:
                logging.info(f"DEBUG: Skipping data of type: {type(data)}")
                return commits

        except Exception as e:
            logging.error(f"DEBUG: Error in find_all_commits: {str(e)}")
            logging.error(f"DEBUG: Error data: {str(data)[:200]}")
            return commits

        return commits

    def _identify_owner_details(self, commits: List[Dict]) -> None:
        """Identify owner details using the following rules:
        1. Any name used with owner's noreply email is owner's name
        2. Any email used with those names is owner's email
        3. Any name matching username is owner's name
        """
        # First find the owner's noreply email and associated names
        for commit in commits:
            author_email = commit["author_email"]
            author_name = commit["author_name"]
            committer_email = commit["committer_email"]
            committer_name = commit["committer_name"]

            # Check author
            if self.username in author_email.lower():
                self.owner_name_email_pairs.add((author_name, author_email))
                self.owner_identities.add(author_name.lower())

            # Check committer
            if self.username in committer_email.lower():
                self.owner_name_email_pairs.add((committer_name, committer_email))
                self.owner_identities.add(committer_name.lower())

        # Second pass: find all emails used with owner names
        changed = True
        while changed:
            changed = False
            for commit in commits:
                author_email = commit["author_email"]
                author_name = commit["author_name"]
                committer_email = commit["committer_email"]
                committer_name = commit["committer_name"]

                # If we find a known owner name, add its email
                if author_name.lower() in self.owner_identities:
                    if (author_name, author_email) not in self.owner_name_email_pairs:
                        self.owner_name_email_pairs.add((author_name, author_email))
                        changed = True

                if committer_name.lower() in self.owner_identities:
                    if (committer_name, committer_email) not in self.owner_name_email_pairs:
                        self.owner_name_email_pairs.add((committer_name, committer_email))
                        changed = True

                # If we find a known owner email, add its name
                for _, known_email in self.owner_name_email_pairs:
                    if author_email.lower() == known_email.lower():
                        self.owner_identities.add(author_name.lower())
                    if committer_email.lower() == known_email.lower():
                        self.owner_identities.add(committer_name.lower())

    def is_contributor(self, name: str, email: str) -> bool:
        """
        Check if a name-email pair belongs to a contributor.
        Handle variations between commit names and GitHub usernames.
        """
        name_lower = name.lower()
        email_lower = email.lower()

        # Start with exact matches
        if name_lower in self.all_contributors:
            return True

        # Check email username part
        email_username = email_lower.split("@")[0]
        if email_username in self.all_contributors:
            return True

        # Check noreply email
        if "@users.noreply.github.com" in email_lower:
            try:
                # Handle both formats:
                # 1. 123456+username@users.noreply.github.com
                # 2. username@users.noreply.github.com
                if "+" in email_lower:
                    username = email_lower.split("+")[1].split("@")[0]
                else:
                    username = email_lower.split("@")[0]
                if username in self.all_contributors:
                    return True
            except:
                pass

        # Special handling for known variations
        for contributor in self.all_contributors:
            # Handle variations like "johndoe" -> "doe"
            if contributor.startswith(name_lower) or name_lower.startswith(contributor):
                return True

            # Handle variations like "John Doe" -> "johndoe"
            name_no_spaces = name_lower.replace(" ", "")
            if name_no_spaces == contributor or contributor in name_no_spaces:
                return True

            # Handle variations in email usernames
            if contributor.startswith(email_username) or email_username.startswith(contributor):
                return True

        return False

    def categorize_emails(
        self, commits_data: Dict[str, List[Dict]]
    ) -> Dict[str, List[Dict]]:
        """Collect and categorize all unique emails."""
        try:
            # Find all commits
            all_commits = self.find_all_commits(commits_data)

            # First collect all unique name-email pairs
            unique_pairs = set()
            for i, commit in enumerate(all_commits):
                try:                    
                    author_email = commit.get("author_email", "")
                    author_name = commit.get("author_name", "")
                    committer_email = commit.get("committer_email", "")
                    committer_name = commit.get("committer_name", "")

                    if author_email and author_name:
                        unique_pairs.add((author_name, author_email))
                    if committer_email and committer_name:
                        unique_pairs.add((committer_name, committer_email))
                except Exception as e:
                    logging.info(f"DEBUG: Error processing commit {i}: {str(e)}")
                    logging.info(f"DEBUG: Problematic commit data: {str(commit)[:200]}")
                    continue

            logging.info(f"DEBUG: Found {len(unique_pairs)} unique name-email pairs")

            # Identify owner details
            self._identify_owner_details(all_commits)

            # Prepare categorized structure
            categorized = {
                "owner_emails": [],
                "contributors_emails": [],
                "other_emails": [],
            }

            # Categorize each unique name-email pair
            for name, email in unique_pairs:
                # Skip GitHub system email
                if email == "noreply@github.com" and name == "GitHub":
                    continue

                # Check if this is an owner pair
                if (name, email) in self.owner_name_email_pairs:
                    categorized["owner_emails"].append({"email": email, "name": name})
                    continue

                # Check if this is a contributor
                if self.is_contributor(name, email):
                    categorized["contributors_emails"].append(
                        {"email": email, "name": name}
                    )
                    continue

                # Everything else goes to other
                categorized["other_emails"].append({"email": email, "name": name})

            # Sort each category
            for category in categorized:
                categorized[category].sort(key=lambda x: (x["email"], x["name"]))

            return categorized
        except Exception as e:
            logging.info(f"DEBUG: Error in categorize_emails: {str(e)}")
            logging.info(f"DEBUG: Error data: {str(commits_data)[:200]}")
            # Return empty categorized structure instead of failing
            return {
                "owner_emails": [],
                "contributors_emails": [],
                "other_emails": [],
            }