# Decisions

Each choice with a default. Change any of them; write what you chose under "Our choices" at the end.

## Architecture
A (API bot), B (Claude Code bridge) or C (Managed Agents). See `architecture.md`.
**Default: A.** Smallest blast radius, and its gate, approval and alarm parts carry over if you move to B.

## Hosting
The machine the bot runs on is the machine it can operate. A small always-on VPS or home server is enough
for option A without voice. Voice with faster-whisper on CPU needs more RAM and CPU; test before buying.
**Default: the server you want to manage, as a dedicated non-root user.**

## Polling or webhook
Long polling (`getUpdates`) needs no public URL and no TLS. A webhook needs an HTTPS endpoint.
Telegram keeps unconfirmed updates up to 24 hours either way.
**Default: long polling.** Revisit only if you run several bots behind one web server.

## Model and effort
`MODEL` env var. `claude-opus-5-5` is the default here. It always thinks; `EFFORT` sets how hard
(`low` is fine for chat, `medium` default). Smaller models cost less per token; check the models and
pricing pages at https://platform.claude.com/docs. Server-side fallbacks are on by default for
`claude-opus-5-5` (`USE_FALLBACKS`).
**Default: claude-opus-5-5, effort medium. Try low for everyday chat and compare.**

## Transcription
Local faster-whisper (free, private, uses your CPU/GPU) or a hosted speech-to-text API (fast, costs money,
audio leaves your machine). Model size trades speed for accuracy; dialects often need a larger model.
**Default: local faster-whisper, `small` on CPU; move up only if transcripts are wrong.**

## Storage
JSON files in `STATE_DIR`: `pending.json` (paused approvals) and `history.json` (last 20 messages per chat,
text only). Enough for one owner. Move to SQLite if several people use it or files grow.
**Default: JSON files, mode 600.**

## Conversation memory
The starter keeps the last 20 plain-text messages per chat. No tool details, no thinking. Older context is dropped.
**Default: keep it. Add a `/forget` command if you want a manual reset.**

## Scheduler for the brief
cron, a systemd timer, or a workflow tool you already run. Must be plain code, not the model.
**Default: systemd timer (logs in journalctl, catches up after downtime with `Persistent=true`).**

## Alarm channel
A second Telegram bot, email, SMS, or a push service. It must not share a failure point you care about.
**Default: a second Telegram bot token called by a plain script.** It still depends on Telegram;
add email if that matters to you.

## Who may use it
`ALLOWED_USER_IDS`. More users means more to think about: whose approval counts, shared history.
**Default: the owner only.**

---

## Our choices

(Claude fills this in with the owner during the "Make it yours" questions.)

- Machine:
- Architecture:
- READ tools:
- ACT tools:
- Users:
- Voice languages / GPU:
- Brief time, timezone, sources:
- Alarm events:
- Monthly budget:
- Measured: transcription time for 10 s of audio:
