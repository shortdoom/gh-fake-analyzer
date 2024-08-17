# Github Profile Analyzer

Download and analyze profile data of any user or organization on GitHub. A reconnaissance tool for OSINT/security community, use to inspect for dark patterns in potential bot/scammer/blackhat/fake-employee type of accounts.

### Install

Rename `.env.example` to `.env` and supply your GitHub API Key (generated in your profile). If you don't, the script will use global API limits (slow). 

<small><i>Optionally, rename `targets.example` to `targets` and supply list of profiles to analyze.</i></small>

<small><i>Github API tokens are only alive for 30 days, you'll need to regenerate your token after that time.</i></small>
 
### Run

```sh
   pip install -r requirements.txt
   python analyze.py <username> # analyze a single user

   # Optional
   python analyze.py # read from "targets" and analyze all
   python analyze.py <username> --commit_search # search github for commit messages (slow, experimental)
   python analyze.py --targets <path> # custom_file.txt to read from as "targets"   
```

A `script.log` file is created after the first run. All profile data is downloaded to `/out`.

# How to Read the Output

Inside the `/out` directory, there will be a `<username>` subdirectory for each account scanned.

Report file is main output file, `{username}.json` file is the full data dump (can be long). Cross-search both files for the best effect.

- The `{username}.json` file contains the user's profile data, all repositories hosted on the user's account (forked and not), all commit data (including commit messages to any repositories hosted on the user's account), as well as following and followers data. The `date_filter` will only be non-empty if a suspicious flag is raised (experimental, low confidence). The `commit_filter` will only be present if `--commit_search` flag was used.

- The `report.json` is built on top off `{username}.json` file. Additionally, it contains more of external data for profile, such as the user's pull requests created to any repository, as well as commits added to any repository (including repositories not hosted on the user's account). It also contains a list of `unique_emails` (emails of contributors to the user's hosted repositories) extracted from the commit data. Additionally, for easier access, followers/following data is repeated as a GitHub URL.

IMPORTANT NOTE: The `unique_emails` in `report.json` are not limited to the repository owner's emails. This list may include emails of external contributors to the repository or even completely spoofed emails. Copy the email address and search `{username}.json` for it to get the exact commit where e-mail was used. It may be far-detached from the account you're analyzing.

- The `failed_repos.json` file inside the subdirectory will contain data on repositories that the script failed to `git clone`. There are many reasons why this can happen, such as network errors or DMCA takedowns.

It's best to navigate all files to get a clearer picture of the user's activity.

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

[shortdoom analysis](/profiles/shortdoom/shortdoom.json)

[shortdoom report](/profiles/shortdoom/report.json)

### Features of Skid accounts

For Skid accounts - Example: eduales99 and sebastian4098

1. Commits before the creation date of acount (all eduales99 repositories)
2. Weird contribution from sebastian4098 to a single repo, sebastian4098 itself is suspicious account
3. Weird non-owner emails as authors/contributors to owner repositories, indicates many accounts used for setting up this profile
4. Copied commit messages from real repository
5. DMCA takedown on a repository (mirrored real repository)

Basically, Skids are retarded. They buy accounts from some farms, and farms themselves only run those accounts in automatic way, breadcrumbs to follow are everywhere. A further modeling would probably unearth some dark patterns of such clusters.

[eduales99 analysis](/profiles/eduales99/eduales99.json)

[eduales99 report](/profiles/eduales99/report.json)

[sebastian4098 analysis](/profiles/sebastian4098/sebastian4098.json)

[sebastian4098 report](/profiles/sebastian4098/report.json)

### Features of DPRK-style accounts

For DPRK-style - Example: light-fury

1. No commits before the account creation date. Probably an old stolen GitHub account (for light-fury we can find sergeypt423 that made the first commit to this account in 2017, points to Kenyan freelancer forum).
2. Weird contributions by many accounts to some fairly big projects like GaimzWeb/Mobile, but this is not neccessarily a red flag, regular accounts can be similar
3. A ton of different emails in commit messages. A strong cluster of many accounts "working together" to boost light-fury's credibility.
4. No commit messages copied

Very hard to distinguish from the regular accounts, but there are some flags. Analyzing clusters of activity on such account and checking the merit of their work is basically the only way to distinguish DPRK-style hacker from regular account.

[light-fury analysis](/profiles/light-furty/light-fury.json)

[light-fury report](/profiles/light-fury/report.json)
