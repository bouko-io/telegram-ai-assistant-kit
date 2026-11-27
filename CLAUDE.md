# CLAUDE.md: guiding stones for building a Telegram AI assistant

You are helping one person build their own private Telegram assistant. This repo is a starting
point, not a product. Make it theirs. Keep it small enough that they can read all of it.

## Goal

A Telegram bot that only its owner can use. It understands text and voice notes, answers with
Claude, looks at things freely (READ tools), and changes things only after the owner taps
Approve (ACT tools). Optionally: a morning brief on a schedule, and an alarm channel that works
even when the model does not.

## Ask before building (Make it yours)

Ask these first, one short group at a time. Write the answers into `docs/decisions.md`
under "Our choices". Do not start M2 until they are answered.

1. What machine will it run on? (VPS, home server, laptop.) Is it always on?
2. Which architecture: A (API bot, this starter), B (Claude Code on the server), or C (Managed Agents)?
   Read `docs/architecture.md` with them if unsure. Default: A.
3. What should it be able to SEE? (disk, services, logs, calendar, inbox, a database, a website status)
4. What should it be able to DO, after approval? List each action. Anything not listed is not built.
5. Who besides the owner may use it, if anyone?
6. Which languages or dialects for voice notes? Is a GPU available?
7. Morning brief: yes or no; what time and timezone; which sources?
8. Which events are critical enough for the alarm channel (bypassing the model)?
9. Monthly spend they are comfortable with for the API, so you can pick model and effort.

## Principles

- **Owner only.** Check `from.id` against `ALLOWED_USER_IDS` on every message AND every button tap.
  Fail closed: empty allowlist means the bot does not start.
- **READ runs, ACT asks.** A tool that changes anything (restart, write, send, delete, pay) is ACT.
  When unsure, it is ACT. ACT tools run only after a tap on Approve from an allowlisted user.
- **The model picks from a menu.** Tools take names from allowlists or enums. No tool takes a raw
  shell string. No `shell=True`. Fixed argv, timeouts.
- **Dry run first.** New ACT tools ship with `ACT_DRY_RUN=true`. The owner flips it after watching it work.
- **Plain code for what must not fail.** Allowlist checks, approval, alarms and schedules are code,
  not prompt instructions. The model is never the only gate between a critical event and the owner.
- **Docs first.** Before calling any new API, read its official docs and note auth, quota per minute
  and per day, free-tier limits, error shape (some return HTTP 200 with an error inside), pagination.
  Write each non-obvious limit as a comment at the line it constrains, with "(docs read YYYY-MM-DD)".
- **Secrets from the environment only.** `.env` stays out of git. Never print a token in logs or replies.
- **Small.** Prefer one more small file over a framework. The owner should be able to read every line.

## Guardrails (do not)

- Do not add a "run any command" tool to option A. If they want that, it is option B, with its own controls.
- Do not let a declined action be retried in the same turn. The tool_result says declined; respect it.
- Do not put timestamps or changing text in the system prompt or tool list (it breaks prompt caching).
  Put the date in the user message if needed.
- Do not send `temperature`, `top_p`, `thinking: disabled`, `budget_tokens`, or a forced `tool_choice`
  to `claude-opus-5-5`: the API rejects them (400). Use `output_config={"effort": ...}`.
- Do not read a `refusal` stop reason as an answer.
- Do not set a webhook while using long polling (getUpdates stops working).
- Do not commit `.env`, `state/`, logs or transcripts.
- Do not call real APIs from tests. Use the fakes in `starter/tests/conftest.py`.

## Build order

Follow `docs/build-plan.md`: M0 (tests green) -> M1 (first real reply) -> M2 (their READ tools) ->
M3 (their ACT tools, dry run, then live) -> M4 (voice) -> M5 (morning brief) -> M6 (alarm channel) ->
M7 (run as a service). One milestone at a time. Show the "done when" check passing before moving on.
Use `/next-milestone` and `/check`.

## Definition of done (for each change)

- `make check` passes.
- New tools have a test: READ runs at once, ACT waits for approval, decline path never runs it.
- New API limits are commented in code with the date read.
- `grep -rnE "sk-an[t]-|bot[0-9]{6,}:" --exclude-dir=.venv --exclude=.env .` finds nothing (no keys in the repo).
- The owner has seen it work on their phone (not just in tests).
- README "What the starter does today" is still true.

## Where things are

- `starter/bot.py`: polling loop, allowlist, voice handling, button taps.
- `starter/agent.py`: Claude call, tool loop, pending approvals (`state/pending.json`), chat history.
- `starter/tools.py`: tool registry. Add tools here. Each has a `kind`: READ or ACT.
- `starter/telegram.py`: Bot API client, message splitting, button helper.
- `starter/voice.py`: transcriber interface and optional faster-whisper.
- `prompts/system.md`: system prompt template; fill it and set `SYSTEM_PROMPT_FILE`.
