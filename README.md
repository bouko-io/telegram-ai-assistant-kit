# Telegram AI assistant (starter kit)

A private Telegram bot that talks to Claude, can look at your server, and asks before it changes anything.

This repo is a set of guiding stones for your own Claude Code: principles, architecture options,
a build plan with checks, prompts, and a small starter that runs. You build your own version.

## What you get

- `CLAUDE.md`: instructions your Claude Code follows while it builds with you.
- `START-HERE.md`: one prompt to paste into Claude Code to begin.
- `docs/`: architecture options, build plan (M0 to M6), decisions, safety, recipes.
- `prompts/`: system prompt template and task prompts.
- `.claude/commands/`: `/next-milestone`, `/check`, `/add-tool` for Claude Code.
- `starter/`: about 770 lines of Python (comments included) plus 37 tests that run without network or keys.

What the starter does today:

- Answers only allowlisted Telegram user ids. Everyone else is ignored.
- Text in, Claude answers, Claude can call tools.
- READ tools (disk usage, uptime) run at once.
- ACT tools (restart an allowlisted systemd service) show Approve / Decline buttons and run only after a tap.
  Dry run by default.
- Pending approvals live in a JSON file, so they survive a restart.
- Voice notes: hook is there, off by default. Turn on with the voice recipe.

Not in the starter (recipes in `docs/recipes/`): morning brief, local Whisper setup,
more server tools, a separate alarm channel.

## Who it is for

Someone who runs a server (a VPS, a home box) and wants to check and fix it from a phone.
You do not need to be a developer, but you need Claude Code and a terminal on that server.

## 15-minute start

1. Talk to `@BotFather` in Telegram, create a bot, copy the token.
2. Create an API key in the Claude Console: https://platform.claude.com
3. On your server:
   ```bash
   cp .env.example .env        # then fill TELEGRAM_BOT_TOKEN and ANTHROPIC_API_KEY
   make venv
   make check                  # 37 tests, no network
   ```
4. Find your Telegram user id. The bot refuses to start with an empty `ALLOWED_USER_IDS`, so put
   a placeholder (`1`), run `make run`, send the bot a message, and read the log line
   `ignored message from user id <your id>`. Put that id in `.env` and restart.
5. Send "how full is the disk?". Then "restart web" with `ALLOWED_SERVICES=web`: you get buttons,
   and with `ACT_DRY_RUN=true` nothing is restarted.

Or open Claude Code in this folder and paste the prompt from `START-HERE.md`.

## How it works

```
 phone (Telegram)                         your server
 ----------------                         -----------------------------------------
 text / voice  --->  Telegram Bot API <--- bot.py  long polling (getUpdates)
                                             |  allowlist check (user id)
                                             |  voice -> transcriber (optional)
                                             v
                                           agent.py  ---- messages + tools ---->  Claude API
                                             |       <--- answer or tool_use -----
                                             |
                                 READ tool --+--> run now, send result back to Claude
                                 ACT tool  --+--> save pending.json, send Approve/Decline
                                             |
 tap Approve  --->  callback_query  ------> decide(): run tool (or "declined"), resume loop
                                             v
 answer      <---------------------------  sendMessage (split at 4096)
```

Two other shapes (Claude Code on the server, or Claude Managed Agents) are in `docs/architecture.md`.

## Costs and limits

- Claude API: billed per token. See the pricing page linked from https://platform.claude.com/docs.
  This kit does not state prices because they change.
- Telegram Bot API: free. Limits from https://core.telegram.org/bots/faq (read 2026-11-27):
  avoid more than about 1 message per second in one chat; bots can download files up to 20 MB;
  messages are 1 to 4096 characters; button `callback_data` is 1 to 64 bytes.
- Local Whisper (faster-whisper): free, uses your CPU or GPU. Speed on your machine is untested here.

## Safety

The short version: allowlist by user id, READ vs ACT tools, approval before any change,
commands chosen from a list you wrote (never a free shell), dry run first, secrets in `.env`,
and a separate alarm path that does not depend on the model. Details: `docs/safety.md`.

## FAQ

**Can it run any shell command?** Not in the starter, on purpose. Every ACT tool is a fixed command
with an allowlisted argument. If you want a broader agent, see option B in `docs/architecture.md`
and read its safety notes first.

**Why long polling and not a webhook?** No public URL or TLS certificate needed. One process, works
behind a home router. A webhook is a later choice (see `docs/decisions.md`).

**What if Claude is down?** The bot replies with the error. Alerts that matter must not depend on it:
see `docs/recipes/alarm-channel.md`.

**Does it understand my dialect?** Whisper's quality varies by language and accent. The bot echoes
"Heard: ..." so you can see what it understood before anything happens. Test with your own voice.

**Is this tested against the real APIs?** The unit tests use fakes. The request shapes follow the
docs as read on 2026-11-27. Your first real run is the real test (milestone M1 in the build plan).

## License

MIT, see `LICENSE`.
