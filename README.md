# Github Profile Analyzer (and database)

Download, analyze or monitor profile data of any GitHub user or organization. This reconnaissance tool is designed for the OSINT/security community, enabling the inspection of potential bot, scammer, blackhat, or fake employee accounts for dark patterns (see, [Malicious GitHub Accounts](#malicious-github-accounts))

**Disclaimer:** The information provided here **may** be incorrect. Please do not make any (baseless) accusations based on this content. All information is sourced from publicly available third-party sources and verified to the best of my ability (only).

### Install

Scripts require `git` to be installed on your OS. (`sudo apt install git`)

Rename `.env.example` to `.env` and supply your GitHub API Key (generated in your profile). If you don't, the script will use global API limits (slow).

<small><i>Github API tokens have time-to-live, you'll need to regenerate your token after that time.</i></small>

Only development version is available now. PyPi package is in progress.

Setup the new `venv`, then:

```sh
pip install git+https://github.com/shortdoom/gh-fake-analyzer.git

# alternatively:

git clone https://github.com/shortdoom/gh-fake-analyzer.git
cd gh-fake-analyzer
pip install -e . # remember about venv!
```

### Analyze user

The `gh-analyze` is designed to download full github profile data of specified user, see [Output](#output) for details.

```sh
gh-analyze <username> # analyze a single user
gh-analyze <username> --out_path /path/to/dir # save to different than /out dir
gh-analyze --targets <path> # custom_file.txt to read from as "targets"   
gh-analyze <username> --commit_search # search github for commit messages (slow, experimental)
gh-analyze <username> --token <token> # provide GH_TOKEN to use for this run
```

A `script.log` file is created after the first run in the current working directory of the pacakge. All profile data is downloaded to `out` directory within the current working directory.

- The default configuration is at `~/.gh_fake_analyzer_config.ini`
- To use a local configuration, create a `config.ini` file in your working directory.
- Use this file to set different MAX parameters (e.g., for accounts with large amounts of data, especially followers/following).

### Monitor user

The `gh-monitor` is designed to continously monitor the activity of specified Gituhb users. It works as an event watcher. On first run, it will return last past 90 days of events for an account.

```sh

gh-monitor --username <username> # Monitor single user
gh-monitor --targets <file> # Monitor multiple usernames

```

Activity is logged to both `monitoring.log` file and terminal. It captures various events such as:

- New followers
- Profile updates (e.g., changes in name, company, blog, location, email, bio, Twitter username)
- GitHub events (e.g., stars, pushes, forks, issues, pull requests)

# Output

Inside the `/out` directory, there will be a `<username>` subdirectory for each account scanned.

`report.json`, is the output file, see the [report_example.json](/profiles/INVESTIGATIONS/report_example.json) to get a short overview of all keys and potential values in the report.

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

IMPORTANT NOTE: The `unique_emails` in `report.json` are not limited to the repository owner's emails. This list may include emails of external contributors to the repository or even completely spoofed emails. Copy the email address and search `{username}.json` for it to get the exact commit where e-mail was used. It may be far-detached from the account you're analyzing.

# Malicious Github Accounts

DISCLAIMER: The confidence in detecting "malicious" GitHub profiles is low. Many regular user accounts may appear in the analysis files; this does not indicate their participation in any illegal activity. ANYBODY can edit the `.git` file, and ANYBODY can commit code to GitHub. This tool is intended for reconnaissance purposes only.

It's possible, to a certain degree, to define some metrics for classifying GitHub profiles as potentially malicious. However, motivated enough attackers can still bypass most of those checks and appear as professional engineers. If that's the case, a company should fall back to regular methods of judging a potential employee/contact. The following script can help out with finding some dark patterns if the attacker is not motivated enough :)

1. Does any (not forked) repository or commit predate the account creation date? If yes - suspicious.
2. Does any (not forked) repository have more contributors than the owner? If yes - check contributors; it can be suspicious on small accounts.
3. How many unique emails do you find in commit messages? If many - suspicious; account used on many different PCs with many different credentials.
4. Does any commit message appear copied from another repository? If yes - suspicious; owner probably copied the original repository and edited .git history.
5. While getting "all repositories" for an onwer account, do some repositories return an error with DMCA takedown? If yes, suspicious.

Great list of flags by ZachXBT: https://x.com/zachxbt/status/1824047480121729425

Some indicators teams can look out for in the future includes: 

1) They refer each other for roles 
2) Good looking resumes / GitHub activity although sometimes lie about work history. 
3) Typically are happy to KYC but submit fake IDs in hopes teams do not investigate further
4) Ask specific questions about locations they claim to be from. 
5) Dev is fired and immediately new accounts appear looking for work
6) May be good devs initially but typically start to underperform
7) Review logs
8) Like using popular NFT pfps 
9) Asia accent

# Regular, Skid and DPRK-style profile (WIP)

Heuristics here is only informational. There can be a lot of edge cases, false positives and false negatives both happen and are hard to deduce from report files, the following are nothing else than a list of rules-of-thumb.

### Features of regular accounts

For Regular accounts I've ran the analysis on my own profile

1. No commits before the account creation date
2. Contributors (to the owner's repositories) are none/small amount and if there are any, the contributor profile itself is not suspicious
3. Very little unique mails in commit messages, one machine/account used
4. No commit messages copied
5. No DMCA takedowns


### Features of Skid accounts

For Skid accounts - Example: eduales99 and sebastian4098

1. Commits before the creation date of acount (all eduales99 repositories)
2. Weird contribution from sebastian4098 to a single repo, sebastian4098 itself is suspicious account
3. Weird non-owner emails as authors/contributors to owner repositories, indicates many accounts used for setting up this profile
4. Copied commit messages from real repository
5. DMCA takedown on a repository (mirrored real repository)

Basically, Skids are retarded. They buy accounts from some farms, and farms themselves only run those accounts in automatic way, breadcrumbs to follow are everywhere. A further modeling would probably unearth some dark patterns of such clusters.

[eduales99 analysis](/profiles/INVESTIGATIONS/ContagiousInterview_00.00.2024/eduales99/eduales99.json)

[eduales99 report](/profiles/INVESTIGATIONS/ContagiousInterview_00.00.2024/eduales99/report.json)

[sebastian4098 analysis](/profiles/INVESTIGATIONS/ContagiousInterview_00.00.2024/sebastian4098/sebastian4098.json)

[sebastian4098 report](/profiles/INVESTIGATIONS/ContagiousInterview_00.00.2024/sebastian4098/report.json)

### Features of DPRK-style accounts

For DPRK-style - Example: light-fury

1. No commits before the account creation date. Probably an old stolen GitHub account (for light-fury we can find sergeypt423 that made the first commit to this account in 2017, points to Kenyan freelancer forum).
2. Weird contributions by many accounts to some fairly big projects like GaimzWeb/Mobile, but this is not neccessarily a red flag, regular accounts can be similar
3. A ton of different emails in commit messages. A strong cluster of many accounts "working together" to boost light-fury's credibility.
4. No commit messages copied

Very hard to distinguish from the regular accounts, but there are some flags. Analyzing clusters of activity on such account and checking the merit of their work is basically the only way to distinguish DPRK-style hacker from regular account.

[light-fury analysis](/profiles/INVESTIGATIONS/ContagiousInterview_00.00.2024/light-fury/light-fury.json)

[light-fury report](/profiles/INVESTIGATIONS/ContagiousInterview_00.00.2024/light-fury/report.json)

### Dev notes

Repository hosts a data dump of suspicious github accounts in `/profiles` directory. Because of this, size of repository is pretty large. Use something like below to only grab package code:

```sh
git clone --filter=blob:none --sparse https://github.com/shortdoom/gh-fake-analyzer && cd gh-fake-analyzer && git sparse-checkout set --no-cone '*' '!profiles'
```