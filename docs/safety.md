# Safety

Threats specific to a phone-controlled assistant on your own server, and the control for each.
"Starter" means the control is already in the code.

| Threat | What could happen | Control |
|---|---|---|
| A stranger finds the bot | Anyone who knows or guesses the bot username can message it. | Allowlist on `from.id` for messages AND button taps; strangers get no reply. Starter. |
| Empty or wrong allowlist | Bot answers everyone, or no one | Config refuses to start with an empty list. Starter. |
| Someone else taps Approve | In a group, anyone can press buttons | Callback `from.id` checked too. Starter (`test_stranger_cannot_press_approve`). |
| Model does something you did not ask | Restart, delete, send | Every change is an ACT tool; runs only after a tap. Declined actions return an error result. Starter. |
| Model chooses the command | Shell injection through a tool argument | Tools take names from an allowlist + strict pattern, fixed argv, no shell, timeout. Starter (`restart_service`). |
| Prompt injection | Text in a log, email or web page tells Claude to act | Same as above: the worst it can do is propose an ACT, which you see and decline. Read the approval text before tapping. |
| Approval fatigue | You tap Approve without reading | Approval text shows the exact action and input. Keep ACT tools few and specific. Dry run first. |
| Bad transcription | A voice note is heard wrong and triggers the wrong action | "Heard: ..." echo before Claude answers; ACT still needs a tap. Starter. |
| Stale approval | You tap a button from yesterday | Each pending request is single-use; a second tap says expired. Add an expiry if you want (recipe idea). |
| Token leak | Bot token in logs, error messages, git | Tokens only from env; httpx request logging silenced (URLs contain the token); file download errors do not include the URL; `.env*` gitignored. Starter. |
| API key leak | Key in code or chat | `ANTHROPIC_API_KEY` from env only. Never paste it into a chat with Claude. |
| Bot runs as root | Any bug becomes a root bug | Run as a dedicated user. Grant only the exact commands via sudoers (recipe). |
| Model or API down | You miss a real incident | Alarm channel by plain code, no model in the path (recipe). |
| Telegram flood limits | Messages dropped with 429 | Client paces to ~1 message/second per chat and surfaces `retry_after`. Starter. |
| Personal data in transcripts | History and pending files hold your messages | `state/` gitignored, files written mode 600. Delete `history.json` any time. Starter. |
| Option B (Claude Code) | Broad shell access | Dedicated user, `--allowedTools` rules, `dontAsk` mode for unattended runs, never `bypassPermissions` outside an isolated VM. See `architecture.md`. |

## Rules of thumb

- If a tool can lose data, cost money or message someone, it is ACT.
- Start every ACT tool in dry run and watch it for a few days.
- Your approval is the control. If you would not approve it on a screen this small, make the tool smaller.
