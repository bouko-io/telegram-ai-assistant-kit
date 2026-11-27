# Architecture

## Components (all options)

| Part | Job | In the starter |
|---|---|---|
| Telegram bot | Receives messages and button taps, sends replies | `bot.py`, `telegram.py` |
| Gate | Drops anyone not on the allowlist | `handle_update()` in `bot.py` |
| Transcriber | Voice note -> text. Pluggable | `voice.py` (off by default) |
| Agent loop | Sends the conversation to Claude, runs tools, repeats | `agent.py` |
| Tools | READ (look) and ACT (change) | `tools.py` |
| Approval store | Remembers a paused loop until the owner taps | `state/pending.json` |
| Scheduler | Starts the morning brief | cron or a systemd timer (recipe) |
| Alarm | Sends critical alerts by plain code | separate script (recipe) |

## Data flow (option A)

1. `getUpdates` long-polls Telegram (50 s). Each update is confirmed by sending `offset = update_id + 1` next time.
2. Gate: `message.from.id` or `callback_query.from.id` must be in `ALLOWED_USER_IDS`.
3. Voice: `getFile` -> download (max 20 MB) -> transcriber -> "Heard: ..." echo -> text.
4. Agent: history (plain text of the last 20 messages) + new text -> `messages.create` with the tool list.
5. If Claude asks for tools:
   - READ tools run now. Results go back in one user message with all `tool_result` blocks.
   - If any ACT tool is in the turn, the whole turn pauses. The conversation, the tool_use ids and the
     READ results are saved to `pending.json`. One message per ACT tool with Approve / Decline.
6. Tap: answer the callback, record the decision. When every ACT in that turn is decided, run the
   approved ones, mark the declined ones `"The user declined this action."` with `is_error: true`,
   and resume the loop.
7. Final text is split at 4096 characters and sent.

## Option A: API bot (this starter)

Your code runs the loop. Claude only sees the tools you wrote.

- Good: you control every tool and every check. Small attack surface. Easy to test with fakes.
  Approval is a real pause, it survives restarts.
- Cost: every capability is code you write. A new kind of task means a new tool.
- Fits: "check and fix a few known things from my phone".

## Option B: Claude Code bridge

The bot passes each request to Claude Code running headless on the server:
`claude -p "<request>" --output-format json`, then sends back the `result` field. Keep the
`session_id` from the JSON and pass `--resume <session_id>` to continue a conversation.
(Claude Code headless docs read 2026-11-27: https://code.claude.com/docs/en/headless)

What the docs say that matters here:

- `--bare` skips hooks, skills, plugins, MCP servers, auto memory and CLAUDE.md discovery. It is the
  recommended mode for scripts and will become the default for `-p`. In bare mode Claude Code uses
  `ANTHROPIC_API_KEY`, not your subscription login. Without `--bare`, a `-p` run loads the project's
  hooks and `.mcp.json` servers with no trust dialog.
- `--allowedTools` uses permission rule syntax, for example `"Read,Bash(systemctl status *)"`.
  The space before `*` matters: `Bash(git diff *)` does not match `git diff-index`.
- Permission modes (`--permission-mode`): `default` (manual), `acceptEdits`, `plan`, `auto` (a classifier
  reviews actions), `dontAsk` (denies anything that would prompt), `bypassPermissions` (only for isolated
  containers or VMs; refuses to run as root; no protection against prompt injection).
- Since v2.1.302 a `-p` run with no mode set starts in manual mode: any call that needs approval is
  denied unless an allow rule, a `PermissionRequest` hook, or `--permission-prompt-tool` approves it.
- `--permission-prompts none` denies anything that would wait on a prompt (for unattended runs).
- JSON output includes `result`, `session_id` and `total_cost_usd` (a client-side estimate).
- Exit code 0 on success, non-zero on failure. SIGTERM ends with 143 and leaves the turn unfinished.

Why approval still matters in B: Claude Code can run shell commands, so its reach is the whole server
account. Permission rules decide what runs without asking; everything else must come back to you.
Two practical shapes:

1. **Read-only runs.** `--permission-mode dontAsk --allowedTools "Read,Bash(df *),Bash(systemctl status *)"`.
   Anything else is denied. For changes, Claude says what it would do; you send a second message, and
   the bot runs a fixed script (option A style ACT tool) after your tap.
2. **Approval over Telegram.** Use a `PermissionRequest` hook or `--permission-prompt-tool` that sends
   Approve / Decline to Telegram and waits for the tap. This is more work and this kit does not include
   code for it; read the hooks and CLI reference pages before building it.

- Good: Claude can handle tasks you did not foresee. Very little tool code.
- Cost: much larger blast radius. Run it as a dedicated user with limited sudo, never as root.
  Prompt injection from logs, web pages or files it reads becomes a real risk.
- Fits: "I want Claude Code in my pocket" for someone who already uses Claude Code on that server.

## Option C: Claude Managed Agents

Anthropic hosts the agent loop and a sandbox; you define the agent and send it messages. It is in beta
and bills session runtime as well as tokens. It does not run on your server, so it cannot operate it
directly; you would expose tools to it. Read https://platform.claude.com/docs before choosing it.
This kit has no code for C.

- Good: no loop to host, sandboxed execution.
- Cost: beta, extra billing dimension, your server is not inside the sandbox.
- Fits: assistants that mostly work on documents or the web, not on your own machine.

## Choosing

| Question | A | B | C |
|---|---|---|---|
| Must operate this server | yes, via your tools | yes, broadly | only via tools you expose |
| Unforeseen tasks | no | yes | yes, in its sandbox |
| Code you maintain | most | least | little |
| Blast radius | small | large | separate |
| Works offline from Anthropic for alarms | alarm recipe either way | same | same |

Start with A even if you want B later: the gate, approval and alarm parts carry over.
