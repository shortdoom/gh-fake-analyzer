# Malicious Github Accounts

It's possible, to a certain degree, to define some metrics for classifying GitHub profiles as potentially malicious. However, motivated enough attackers can still bypass most of those checks and appear as professional engineers. If that's the case, a company should fall back to regular methods of judging a potential employee/contact. The following script can help out with finding some dark patterns if the attacker is not motivated enough :)

1. Does any (not forked) repository or commit predate the account creation date? If yes - suspicious.
2. Does any (not forked) repository have more contributors than the owner? If yes - check contributors; it can be suspicious on small accounts.
3. How many unique emails do you find in commit messages? If many - suspicious; account used on many different PCs with many different credentials.
4. Does any commit message appear copied from another repository? If yes - suspicious; owner probably copied the original repository and edited .git history.
5. While getting "all repositories" for an onwer account, do some repositories return an error with DMCA takedown? If yes, suspicious.

`analyzer.py` performs all of that and outputs into `/out` directory two files. `{username}.json` file contains the full github profile dump and `report.json` contains specific info pertaining to the above. It's best to have both open. Script also downloads `.git` folder of every non-forked repository to parse commit messages without using github API, feel free to remove those after.

to run, do the:

`pip install -r requirements.txt`

`python analyzer.py <username>` - this will run the analysis without searching for commit messages (takes time)

`python analyzer.py <username> --commit_search` - will run search for copied commits (optional)

# Regular, Skid and DPRK-style profile

For Regular accounts I've ran the analysis on my own profile and Tayvano's

### Features of regular accounts

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