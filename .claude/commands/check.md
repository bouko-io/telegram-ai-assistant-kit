---
description: Run tests and safety checks for the assistant, report pass/fail in plain words.
---

Run these from the repo root and report each as PASS or FAIL with one line of detail:

1. Tests: `make check`
2. Secrets not in the repo: `grep -rnE "sk-an[t]-|bot[0-9]{6,}:|ANTHROPIC_API_KE[Y]=[A-Za-z0-9]|TELEGRAM_BOT_TOKE[N]=[0-9]" --exclude-dir=.venv --exclude-dir=.git --exclude=.env .`
   must print nothing.
3. `.env` ignored: `git check-ignore -q .env && echo ignored` (skip if not a git repo, say so).
4. No shell in tools: `grep -n "shell=True" starter/*.py` must print nothing.
5. Every ACT tool has a test where decline means it never ran: list ACT tools in starter/tools.py and
   find the matching tests.
6. Allowlist fails closed: `ALLOWED_USER_IDS=` with a token set must make `load_config()` raise.
7. Dry run status: print the current ACT_DRY_RUN value from .env (value only, never other lines).

End with: what to fix first, if anything.
