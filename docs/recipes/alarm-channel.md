# Recipe: alarm channel (no model in the path)

Critical alerts must reach you even when Claude, your API key, or the main bot is broken. The model is
never the only gate between a critical event and you. This recipe is plain code.

## Design

- A separate script, run by a timer every few minutes (or by the system that detects the event).
- Its own Telegram bot token (`ALARM_BOT_TOKEN`), so a crash or flood limit on the main bot does not
  silence it. Same `OWNER_CHAT_ID`.
- Checks are code: thresholds, "is the service active", "did the brief run today".
- Deduplication: remember what was already sent, so a full disk sends one alarm, not one every 5 minutes.
- Optional: after sending, the main bot can be asked to explain the alarm. That is extra, not the alarm.

## Steps

1. Create a second bot with `@BotFather`. Send it one message from your phone first (bots generally cannot start a chat with you).
2. In `.env`: `ALARM_BOT_TOKEN=`, `OWNER_CHAT_ID=`.
3. Create `starter/alarm.py`:

```python
"""Plain-code alarms. No Claude here, on purpose."""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from telegram import TelegramClient

STATE = Path(os.environ.get("STATE_DIR", "state")) / "alarm_sent.json"
REPEAT_AFTER = 6 * 3600  # re-send an active alarm every 6 h


def checks() -> list[tuple[str, str]]:
    """Return (key, message) for every problem right now."""
    out = []
    u = shutil.disk_usage("/")
    if u.used / u.total > 0.90:
        out.append(("disk_root", f"Disk / is {u.used / u.total:.0%} full"))
    for svc in os.environ.get("ALARM_SERVICES", "").split(","):
        if svc and subprocess.run(["systemctl", "is-active", "--quiet", svc], timeout=10).returncode != 0:
            out.append((f"svc_{svc}", f"Service {svc} is not active"))
    return out


def to_send(problems, sent: dict, now: float) -> list[str]:
    msgs = []
    for key, msg in problems:
        if now - sent.get(key, 0) > REPEAT_AFTER:
            msgs.append(msg)
            sent[key] = now
    active = {k for k, _ in problems}
    for key in list(sent):
        if key not in active:
            del sent[key]  # cleared: alarm again next time it happens
    return msgs


def main():
    sent = json.loads(STATE.read_text()) if STATE.exists() else {}
    msgs = to_send(checks(), sent, time.time())
    if msgs:
        TelegramClient(os.environ["ALARM_BOT_TOKEN"]).send_message(
            int(os.environ["OWNER_CHAT_ID"]), "ALARM\n" + "\n".join(msgs))
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(sent))


if __name__ == "__main__":
    main()
```

4. Test `to_send` without network: same problem twice in a row sends once; cleared then back sends again.
5. Timer: like the brief, with `OnCalendar=*:0/5` (every 5 minutes).
6. Run it from cron or a timer that does not depend on the main bot service being up.

## Limits to know

- It still depends on Telegram and on the server being alive. If the server is down, it cannot alarm.
  For that, use an outside uptime check (any external monitor that pings your server) that alerts you
  by email or SMS.
- Telegram asks bots to stay under about 1 message per second per chat (FAQ read 2026-11-27).
  Batch alarms into one message, as above.

## Done when

- The dedup test passes.
- With `ANTHROPIC_API_KEY` set to an invalid value and the main bot stopped, a forced alarm
  (set the disk threshold to 0.0 for one run) reaches your phone.
