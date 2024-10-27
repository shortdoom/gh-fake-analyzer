# Github Profile Analyzer (and database)

Download, analyze and monitor profile data of any GitHub user or organization. This reconnaissance tool is designed for the OSINT/security community, enabling the inspection of potential bot, scammer, blackhat, or fake employee accounts for dark patterns (see, [Malicious GitHub Accounts](#malicious-github-accounts))

`gh-analyze` is designed to quickly build a dataset with accessible schema of GitHub profiles you are targeting for investigation. It is still a work in progress.

### Install

Scripts require `git` to be installed on your OS. (`sudo apt install git`)

```sh
pip install gh-fake-analyzer
```

You should either create `.env` file in the current working directory with `GH_TOKEN=<your_token>`, run `gh-analyze` with `--token <your_token>` flag or execute `export GH_TOKEN=<your_token>`. If you don't, the script will use global API limits (slow and error-prone).

For development, set the new `venv` and:

```sh
git clone https://github.com/shortdoom/gh-fake-analyzer.git
cd gh-fake-analyzer
pip install -e . # installl_requires only, use requirements.txt for build tools
```

<small><i>Github API tokens have a time-to-live, you'll need to regenerate your token after that time.</i></small>

<small><i>See [Dev Notes](#dev-notes) to only `git clone` package code and not the `/profiles` data.</i></small>

### Analyze user

The `gh-analyze` is designed to download full github profile data of the specified user, see [Output](#output) for details.

```sh
gh-analyze <username> # analyze a single user
gh-analyze --targets <path> # custom_file.txt to read from as "targets"
gh-analyze <username> --out_path /path/to/dir # save to different than /out dir
gh-analyze <username> --commit_search <repo_name> # without <repo_name> it will search all commits
gh-analyze <username> --token <token> # provide GH_TOKEN to use for this run
```

Run `gh-analyze --help` for a full description of arguments. Most of arguments can be chained together.

A `script.log` file is created after the first run in the current working directory of the pacakge. All profile data is downloaded to `out` directory within the current working directory.

- The default configuration is at `~/.gh_fake_analyzer_config.ini`
- To use a local configuration, create a `config.ini` file in your working directory.
- Use this file to set different MAX parameters (e.g., for accounts with large amounts of data, especially followers/following).

```sh
[LIMITS]
MAX_FOLLOWING = 1000 # to dump
MAX_FOLLOWERS = 1000 # to dump
MAX_REPOSITORIES = 1000 # to clone
CLONE_DEPTH = 100 # commit messages to clone
CLONE_BARE = True # do not git clone the whole repository, only .git
MONITOR_SLEEP = 10 # minutes to delay between monitor checks
REMOVE_REPO = True # by default, remove repo codebase after cloning
```

### Monitor user

The `--monitor` flag is designed to continously monitor the activity of specified Gituhb users. It works as an event watcher. On first run, it will return last past 90 days of events for an account.

```sh

gh-analyze <username> --monitor # Monitor single user
gh-analyze --targets <file>  --monitor # Monitor multiple usernames

```

Activity is logged to both `monitoring.log` file and terminal. It captures various events such as:

- New followers
- Profile updates (e.g., changes in name, company, blog, location, email, bio, Twitter username)
- GitHub events (e.g., stars, pushes, forks, issues, pull requests)

# Output

Inside the `/out` directory, there will be a `<username>` subdirectory for each account scanned.

`report.json`, is the output file, see the [report_example.json](/profiles/report_example.json) to get a short overview of all keys and potential values in the report. 

- `profile_info` - basic github user profile data (login, name, location, bio, etc.).
- `original_repos_count` and `forked_repos_count` - counted repositories.
- `unique_emails` - emails and associated names extracted from the commit data.
- `mutual_followers` - list of mutual followers for the account.
- `following` - list of accounts user follows.
- `followers` - list of accounts following the user.
- `repo_list` - list of names of all non-forked repositories on the user account.
- `forked_repo_list` - list of names of all forked repositories on the user account.
- `contributors` - user's repositories and associated contributors to those repositories.
- `pull_requests_to_other_repos` - list of user's pull requests made to repositories.
- `commits_to_other_repos` - list of user's commits made to repositories he doesn't own.
- `repos` - full repository data for every user repository. (big)
- `commits` - full commit data for every user repository. (big)
- `errors` - list of repositories that script failed to retrieve data for (network errors, DMCA..)
- `recent_events` - list of recent events on the analyzed account (last 90 days).
- `issues` - list of issues opened by user.
- `comments` - list of comments to issues made by user.

Script will also download user avatar to the output directory.

Additionally, optional keys in the file, depending on arguments used, can be present:

- `potential_copy` - list of repositories with a first commit date earlier than account creation.
- `commit_filter` - list of repositories with similar/duplicated commit messages across the Github. use `--commit_search` flag to generate a list.

IMPORTANT NOTE: The `unique_emails` in `report.json` are not limited to the repository owner's emails. This list may include emails of external contributors to the repository or even completely spoofed emails. Copy the email address and search `commits` key to get the exact commit where e-mail was used. It may be far-detached from the account you're analyzing.

### Parsing output

It's possible to use CLI for extracting individual key data for any username in the `/out` directory `report.json` files. Parsing supports dot-notation for accessing nested keys, e.g,. `profile_info.location`. 

`--summary` flag will output the basic summary information about the profile based on `report.json` found.

```sh
gh-analyze --parse <username> --key <output_key>
gh-analyze --parse <username> --summary

# a useful method for quick-dumping specific data
gh-analyze --parse <username> --key unique_emails >> dump.txt
```

# Malicious Github Accounts

See [INVESTIGATIONS](/profiles/INVESTIGATIONS/) for some high-confidence accounts dumped using `gh-analyze` tool.

Additionally, here's the list of past investigations done with `gh-fake-analyzer`.

[Network of Fake Recruiter and Developer Accounts Linked to Lazarus](https://medium.com/@-Heiner/cc361074bdc2)

[Lazarus patterns discovered with gh-fake-analyzer](https://github.com/BlockOSINT/-threat-research-and-intelligence-/blob/main/Investigations/suspicious-activity-on-github/North-Korea-sponsored-APT/lazarus-group.md)


**Disclaimer:**  The confidence in detecting "malicious" GitHub profiles is low. Many regular user accounts may appear in the analysis files; this does not indicate their participation in any illegal activity. ANYBODY can edit the `.git` file, and ANYBODY can commit code to GitHub. This tool is intended for reconnaissance purposes only. The information provided here **may** be incorrect. Please do not make any (baseless) accusations based on this content. All information is sourced from publicly available third-party sources and verified to the best of my ability (only).

It's possible, to a certain degree, to define some metrics for classifying GitHub profiles as potentially malicious. However, motivated enough attackers can still bypass most of those checks and appear as professional engineers. If that's the case, a company should fall back to regular methods of judging a potential employee/contact. The `gh-analyze` can help out with finding some dark patterns if the attacker is not motivated enough :)

1. Does any (not forked) repository or commit predate the account creation date? If yes - suspicious.
    - inspect the repository and search on github for similar repositories. it's potentially a copy of other repository
    - non-malicious cases are: rebasing, transfering .git repo between the accounts etc.
2. Does any (not forked) repository have more contributors than the owner? If yes - check contributors;
    - is contributor profile suspicious? check contributors profiles themselves.
    - are contributor contributions meaningful or low-effort all across?
3. How many unique emails do you find in commit messages?
    - non-malicious for fully legitimate accounts
    - can be malicious if you recognize a pattern of:
        - trying to hide the (owner's) identity, changing the identity often, using address/name attached to different person
4. Does any commit message appear copied from another repository? 
    - you need to run `--commit_filter` and inspect `matching_repos` number, look for *unique* commit messages
    - merge commit messages, if copied, often preserve the original owner's nickname
5. While getting "all repositories" for an onwer account, do some repositories return an error with DMCA takedown?
    - non-malicious for fully legitimate accounts
    - DMCA takedowns, deleted repositories and empty repositories, if existing together on the account, may suggest some automation software usage
6. Issue-spamming on high-credibility organizations. Some accounts were collecting "github badges" using this method. After opening an issue on, for example, Ethereum organization, the organization "badge" will be visible on main profile page and account will be credited as a "contributor" to Ethereum organization.
    - do not trust Activity Overview badges blindly, use report files from `gh-analyze` to check the actual commit (if there's any)
7. Look "around" the account, not only on the account. Followers/Following patterns are often a tell-tale.

Great list of (non-technical) flags by ZachXBT: https://x.com/zachxbt/status/1824047480121729425

Some indicators teams can look out for in the future includes:

1. They refer each other for roles
2. Good looking resumes / GitHub activity although sometimes lie about work history.
3. Typically are happy to KYC but submit fake IDs in hopes teams do not investigate further
4. Ask specific questions about locations they claim to be from.
5. Dev is fired and immediately new accounts appear looking for work
6. May be good devs initially but typically start to underperform
7. Review logs
8. Like using popular NFT pfps
9. Asia accent

# Regular, Skid/MaaS and DPRK-style profile

Heuristics here is only informational. There can be a lot of edge cases, false positives and false negatives both happen and are hard to deduce from report files, the following are nothing else than a list of rules-of-thumb. See "External Sources" for attribution details.

*PS. Analysis files follow still the old `gh-analyze` report format.*

### Features of regular accounts

1. No commits before the account creation date
2. Contributors (to the owner's repositories) are none/small amount and if there are any, the contributor profile itself is not suspicious
3. Little amount of unique mails in commit messages, no often identity changes
4. No commit messages copied
5. No DMCA takedowns
6. At least some repositories contain "original" code
7. Non-toxic following/follower patterns, mutual following is present
8. Legit contributors to owner's code

### Features of Skid/Malware-as-a-service accounts

For Skid accounts - Example: eduales99 and sebastian4098

1. Commits before the creation date of acount (all eduales99 repositories)
2. Weird contribution from sebastian4098 to a single repo, sebastian4098 itself is a suspicious account
3. Weird non-owner emails as authors/contributors to owner repositories, indicates many accounts used for setting up/boosting credibility of this profile
4. Copied commit messages from real repository
5. DMCA takedown on a repository (mirrored real repository)

So-called "Farmed accounts". Farms themselves only run those accounts in an automatic way, breadcrumbs to follow are everywhere. Further modeling would probably unearth some dark patterns of such clusters. The best bet is to inspect follower/following pattern and quality of repositories. Farmed accounts usually won't host any original code, a lot of tutorial-level code and overcompensate on profile's README page.

[eduales99 analysis](/profiles/INVESTIGATIONS/ContagiousInterview_00.00.2024/eduales99/eduales99.json)

[eduales99 report](/profiles/INVESTIGATIONS/ContagiousInterview_00.00.2024/eduales99/report.json)

[sebastian4098 analysis](/profiles/INVESTIGATIONS/ContagiousInterview_00.00.2024/sebastian4098/sebastian4098.json)

[sebastian4098 report](/profiles/INVESTIGATIONS/ContagiousInterview_00.00.2024/sebastian4098/report.json)

**External Sources:**

[Contagious Interview](https://github.com/tayvano/lazarus-bluenoroff-research?tab=readme-ov-file#%EF%B8%8F-contagious-interview)

### Features of DPRK-style accounts

For DPRK-style - Example: light-fury, 0xm00neth, bluesky0309

1. No commits before the account creation date. Probably an old stolen GitHub account (for light-fury we can find sergeypt423 that made the first commit to this account in 2017, points to Kenyan freelancer forum). Time series analysis of commits is useful, are there any significant leaps in the activity? 
2. Weird contributions by many accounts to some fairly big projects like GaimzWeb/Mobile, but this is not neccessarily a red flag, regular accounts can be similar, however, project itself seem suspicious.
3. A ton of different emails in commit messages. A strong cluster of many accounts "working together" to boost light-fury's credibility. It's consistent with a pattern of "recommending a friend for a work"
4. No commit messages copied

Very hard to distinguish from the regular account, but there are some flags. Analyzing clusters of activity on such account and checking the merit of their work is basically the only way to distinguish DPRK-style hacker from a regular account. Light-fury was commiting working code to multiple legit organizations at the acceptable level of effort (Whitelisting is therefore not very efficient), same as 0xm00neth and bluesky0309, however, those users were far less careful with building up the history of their accounts and we can spot copied repositories for bluesky0309, sometimes with exact merge messages of the original repository. 

[light-fury analysis](/profiles/INVESTIGATIONS/ContagiousInterview_00.00.2024/light-fury/light-fury.json)

[light-fury report](/profiles/INVESTIGATIONS/ContagiousInterview_00.00.2024/light-fury/report.json)

[0xm00neth analysis](/profiles/INVESTIGATIONS/InteligenceOnChain_17.08.2024/0xm00neth/0xm00neth.json)

[0xm00neth report](/profiles/INVESTIGATIONS/InteligenceOnChain_17.08.2024/0xm00neth/report.json)

[bluesky0309 analysis](/profiles/INVESTIGATIONS/InteligenceOnChain_17.08.2024/bluesky0309/bluesky0309.json)

[bluesky0309 report](/profiles/INVESTIGATIONS/InteligenceOnChain_17.08.2024/bluesky0309/report.json)

**External Sources:**

[Light-fury cluster discussion](https://x.com/tayvano_/status/1824257014639497366)

[0xm00neth cluster discussion](https://x.com/blackbigswan/status/1825247425574863176)

### Dev notes

Repository hosts a data dump of suspicious github accounts in `/profiles` directory. Because of this, size of repository is pretty large. Use something like below to only grab package code:

```sh
git clone --filter=blob:none --sparse https://github.com/shortdoom/gh-fake-analyzer && cd gh-fake-analyzer && git sparse-checkout set --no-cone '*' '!profiles'
```
