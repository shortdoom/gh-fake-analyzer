# Edge case 1

User most likely copied the whole repository by `git clone` then added to already created *remote* through the github UI. `analyzer.py` doesn't catch this edge case (should it even? for bad actors this is revealing) when repository owner just inherits some commits and contributors data.

https://github.com/shortdoom/reviews

Breaks rule 1: Does any (not forked) repository or commit predate the account creation date? If yes - suspicious.
