# Start here

Open Claude Code in this folder (`claude`) and paste this:

```
Read CLAUDE.md, README.md and docs/build-plan.md. I want to build my own private Telegram
assistant from this kit. First ask me the "Make it yours" questions from CLAUDE.md, a few at a
time, and write my answers into docs/decisions.md under "Our choices". Then do milestone M0
(set up the venv, run make check) and show me the result. Do not go past M0 until I say so.
Never ask me to paste API keys into the chat; tell me which line of .env to fill instead.
```

## What happens next

1. Claude asks you about your server, what the bot may see, what it may do, voice, and the brief.
2. It writes your answers down, so later sessions remember them.
3. It sets up `starter/.venv` and runs the 37 tests. No keys needed yet.
4. You type `/next-milestone` to move on. Each milestone ends with a check you can run.
5. M1 is the first real message from your phone. You will need the bot token and API key in `.env` by then.

If something breaks, type `/check`: it runs the tests and the safety checks and tells you what failed.
