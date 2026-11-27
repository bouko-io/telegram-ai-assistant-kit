# Build plan

One milestone at a time. Each ends with checks you can run. Do not skip the "done when".
Commands assume you are in the repo root.

## M0: starter runs locally

- `cp .env.example .env` (leave values empty for now).
- `make venv && make check`

Done when:
- `make check` prints `37 passed` (or more, never fewer).
- `git check-ignore .env starter/.venv starter/state` prints all three (if you use git).

## M1: first real reply

- Fill `TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY`, and your id in `ALLOWED_USER_IDS` (README step 4).
- If the bot ever had a webhook: `curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook"` once.
- `make run`, then send "hello" from your phone.

Done when:
- The bot answers "hello" in under a minute.
- A message from a second Telegram account gets no reply and the log shows `ignored message from user id`.
- `ls starter/state/` shows `history.json`. Delete it and the bot still works (it only forgets the chat).
- `journalctl` or the terminal log does not contain your bot token (the starter silences httpx request logs, which include it).

## M2: your READ tools

- For each thing the owner wants to SEE (from `docs/decisions.md`), add a READ tool in `starter/tools.py`
  (use `/add-tool`). Read the docs of any API it calls first.
- Each tool returns short plain text, under ~2000 characters. Trim logs to the last lines.

Done when:
- Each new tool has a unit test that runs without network.
- Asking on the phone "what is <thing>?" makes Claude call the tool (you see the answer use real values).
- `make check` passes.

## M3: your ACT tools (dry run, then live)

- For each action the owner listed, add an ACT tool with a fixed command and an allowlisted argument.
- Keep `ACT_DRY_RUN=true`. Try each action from the phone: Approve shows "DRY RUN: would run ...",
  Decline makes Claude say it left things alone.
- Give the bot's OS user permission for exactly these commands (see `docs/recipes/server-ops-tools.md`).
- Set `ACT_DRY_RUN=false`, restart, try once for real.

Done when:
- Tests cover: waits for approval, approve runs, decline never runs, name outside the allowlist is refused.
- Restart the bot between sending the request and tapping Approve: the tap still works.
- `test_stranger_cannot_press_approve` passes. If you ever add the bot to a group, repeat that check there with a second account.

## M4: voice notes

Follow `docs/recipes/voice-notes.md`.

Done when:
- A 10-second voice note in each of the owner's languages comes back as "Heard: ..." with the right words.
- You know the time it takes on your machine (write it in `docs/decisions.md`).

## M5: morning brief

Follow `docs/recipes/morning-brief.md`.

Done when:
- `python starter/brief.py` sends one message to your chat.
- The scheduler entry is in place and the brief arrived on its own the next morning.
- The brief agent has no ACT tools (`read_only=True`), checked by a test.

## M6: alarm channel

Follow `docs/recipes/alarm-channel.md`.

Done when:
- With `ANTHROPIC_API_KEY` set to an invalid value, a simulated critical event still reaches your phone.
- The alarm script has its own test that runs with no model at all.

## M7: run as a service

- systemd unit with `Restart=on-failure`, a dedicated user, `WorkingDirectory=` the starter folder.
  Example in `docs/recipes/server-ops-tools.md`.

Done when:
- `sudo systemctl kill <unit>` -> the bot is back within a minute.
- After a reboot the bot answers without you logging in.
- `journalctl -u <unit>` shows no token (search for `bot` followed by digits and a colon).
