import logging
import os
import json

POPULAR_COMMIT_MESSAGES = [
    
    # Build and CI Related
    "ci: update workflow",
    "update ci",
    "fix pipeline",
    "update actions",
    "update workflow",
    "update ci/cd",
    
    # Dependencies
    "build(deps): bump",
    "chore(deps)",
    "update dependencies",
    "deps: update",
    "upgrade dependencies",
    "npm update",
    "yarn upgrade",
    "update packages",
    
    # Common Development Tasks
    "wip: initial implementation",
    "work in progress",
    "todo: implement",
    "draft: initial version",
    "temp commit",
    "checkpoint",
    "save progress",
    "backup",
    
    # Documentation
    "docs: update",
    "update docs",
    "fix documentation",
    "update changelog.md",
    "update contributing.md",
    "update license",
    
    # Common Fix Messages
    "hotfix",
    "quickfix",
    "minor fix",
    "patch",
    "bugfix",
    "fix: typo",
    "fix build",
    "fix error",
    "fix warning",
    "fix lint",
    
    # Clean up
    "clean up code",
    "code cleanup",
    "remove unused",
    "delete old files",
    "formatting",
    "format code",
    
    # Feature Related
    "initial implementation",
    "add feature",
    "implement",
    "new feature",
    
    # Configuration
    "update config",
    "config: update",
    "update settings",
    "update env",
    "update docker",
    "update k8s",
    
    # Testing
    "add tests",
    "update tests",
    "fix failing tests",
    "test: add",
    "test: update",
    
    # Version Control
    "merge develop",
    "merge master",
    "merge main",
    "merge branch",
    "resolve conflicts",
    "cherry-pick",
    "rebase",
    
    # Release Related
    "bump version",
    "release v",
    "prepare release",
    "update version",
    
    # Style and UI
    "style: fix",
    "update styles",
    "ui: update",
    "css updates",
    "design changes",
    
    # Common Non-English
    "更新",  # Update (Chinese/Japanese)
    "修复",  # Fix (Chinese)
    "初始化", # Initialize (Chinese)
    "修正",  # Fix (Japanese)
    "変更",  # Change (Japanese)
    "actualización",  # Update (Spanish)
    "corrección",    # Fix (Spanish)
    
    # Top results from investigations
    "MIT LICENSE",
    "README.md",
    "Update README.md"
    "Initial commit"
    "fake commit"
    "Add files via upload"
    "update"
    "Create README.md"
    "first commit"
    "🔁 Update README"
    "- update README.md"
    "initial commit"
    "Update readme.md"
    "Update index.html"
    "Update changelog"
    "- add README.md"
    "commit"
    "update readme"
    "Refactor"
    "fix"
    "Update"
    "- update .github/workflows/build.yml"
    "- update .github/workflows/build-mingw.yml"
    "Update README."
    "."
    "init"
    "Updates"
    "..."
    "Initialize project using Create React App"
    "➕ Add Image 🖼"
    "🔁 Edit HTML"
    "Update github-metrics.svg - [Skip GitHub Action]"
    "- upload files"
    "update changelog"
    "updated"
    "updated readme"
    "Regenerate build artifacts."
    "design"
    "Create LICENSE"
    "🔄 Update README"
    "cleanup"
    "- update .github/workflows/push.yml"
    "Update style.css"
    "create file"
    "Merge branch 'master' into master"
    "readme"
    "Update readme"
    "- add .github/workflows/build.yml"
    "test"
    "- init"
    "Initial commit from Create Next App"
    "🔁 Refactoring"
    "Update package.json"
    "Merge remote-tracking branch 'origin/master'"
    "Update schema"
    "Update README"
    "add dist"
    "- update index.html"
    "Update tools"
    "fix typo"
    "Initial Commit"
    "changes"
    "Update generated files"
    "プロジェクト ファイルを追加します。"
    "Update diagrams.xml"
    "fixes"
    "Update version"
    "Fix typo"
    "version bump"
    "Fix linters"
    "Merge branch 'main' into main"
    "- update Dockerfile"
    "wip"
    "Update Readme.md"
    "README.md"
    "changed"
    "Updated README"
    "⬆️ Init"
    "lint"
    "Fix tests"
    "init, working"
    "Commit"
    "changed the code"
    "update README"
    "Update .gitignore"
    "bug fixes"
    "fix tests"
    "modified"
    "Update dependencies"
    "sync"
    "Update anime.md"
    "Update requirements.txt"
    "initial"
    "final"
]

# Clutter to remove from profile data
KEYS_TO_REMOVE = [
    "followers_url",
    "following_url",
    "gists_url",
    "starred_url",
    "subscriptions_url",
    "organizations_url",
    "repos_url",
    "events_url",
    "received_events_url",
    "forks_url",
    "keys_url",
    "collaborators_url",
    "teams_url",
    "hooks_url",
    "issue_events_url",
    "assignees_url",
    "branches_url",
    "tags_url",
    "blobs_url",
    "git_tags_url",
    "git_refs_url",
    "trees_url",
    "statuses_url",
    "languages_url",
    "stargazers_url",
    "contributors_url",
    "subscribers_url",
    "subscription_url",
    "commits_url",
    "git_commits_url",
    "comments_url",
    "issue_comment_url",
    "contents_url",
    "compare_url",
    "merges_url",
    "archive_url",
    "downloads_url",
    "issues_url",
    "pulls_url",
    "milestones_url",
    "notifications_url",
    "labels_url",
    "releases_url",
    "deployments_url",
    "git_url",
    "ssh_url",
    "clone_url",
    "svn_url",
]


class DataManager:

    def __init__(self, username, out_path=None):
        self.username = username
        if out_path:
            self.user_dir = os.path.join(out_path, username)
        else:
            self.user_dir = os.path.join(os.getcwd(), "out", username)
        if not os.path.exists(self.user_dir):
            os.makedirs(self.user_dir)

        self.report_file = os.path.join(self.user_dir, "report.json")

    def save_output(self, data):
        try:
            filtered_data = self.remove_unwanted_keys(data)
            self.save_to_json(filtered_data, self.report_file)
            logging.info(f"Data saved to {self.report_file}")
        except Exception as e:
            logging.error(f"Error in save_output: {e}")

    def save_to_json(self, data, filename):
        try:
            with open(filename, "w", encoding="utf-8") as json_file:
                json.dump(data, json_file, indent=4, ensure_ascii=False)
            logging.info(f"Successfully saved data to {filename}")
        except Exception as e:
            logging.error(f"Error in save_to_json for {filename}: {e}")
            raise

    def load_existing(self):
        try:
            if os.path.exists(self.report_file):
                with open(self.report_file, "r", encoding="utf-8") as json_file:
                    return json.load(json_file)
            else:
                logging.info("No existing data file found")
                return None
        except Exception as e:
            logging.error(f"Error in load_existing: {e}")
            return None

    def remove_unwanted_keys(self, data):
        if isinstance(data, dict):
            return {
                key: self.remove_unwanted_keys(value)
                for key, value in data.items()
                if key not in KEYS_TO_REMOVE
            }
        elif isinstance(data, list):
            return [self.remove_unwanted_keys(item) for item in data]
        else:
            return data

    def remove_repos_keys(self, repos):
        cleaned_repos = []
        for repo in repos:
            cleaned_repo = {k: v for k, v in repo.items() if k not in KEYS_TO_REMOVE}

            if "owner" in repo:
                cleaned_repo["owner"] = {"login": repo["owner"].get("login")}
            if "license" in repo and repo["license"]:
                cleaned_repo["license"] = {
                    "key": repo["license"].get("key"),
                    "name": repo["license"].get("name"),
                    "spdx_id": repo["license"].get("spdx_id"),
                }
            cleaned_repos.append(cleaned_repo)
        return cleaned_repos
