# Recipe: morning brief

A message every morning with what you chose to watch. Started by a scheduler (plain code), written by
Claude using READ tools only.

## Steps

1. Decide the sources with the owner (server health, calendar, inbox, a news feed). Each source is a
   READ tool. Read each API's docs first: auth, per-minute and per-day quota, and whether it returns
   errors with HTTP 200. One brief a day costs about one call per source per day; fine
   for most free tiers, but check.
2. Send `/start` to the bot. It replies with this chat's id. Put it in `.env` as `OWNER_CHAT_ID=`.
3. Create `starter/brief.py`:

```python
"""Send the morning brief once. Run by a scheduler."""
import datetime
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from agent import Agent
from config import load_config
from telegram import TelegramClient
from tools import build_tools

load_dotenv()
config = load_config()
agent = Agent(
    client=anthropic.Anthropic(),
    tools=build_tools(config.allowed_services, dry_run=True),
    state_dir=config.state_dir,
    model=config.model,
    effort="low",
    use_fallbacks=config.use_fallbacks,
    read_only=True,  # no ACT tools are even offered to the model
)
template = (Path(__file__).parent.parent / "prompts" / "morning-brief.md").read_text()
# The date goes in the user message, never the system prompt (keeps prompt caching working).
prompt = template.replace("{date}", datetime.date.today().isoformat())
chat_id = int(os.environ["OWNER_CHAT_ID"])
replies = agent.handle_text(chat_id, prompt)
tg = TelegramClient(config.telegram_token)
for r in replies:
    tg.send_message(chat_id, r.text)
```

4. Edit `prompts/morning-brief.md`: replace `{sources}` and `{max_lines}` with your own text.
   Only `{date}` is filled in at run time.
5. Schedule it. systemd timer example (`/etc/systemd/system/assistant-brief.timer` + `.service`):

```ini
# assistant-brief.service
[Service]
Type=oneshot
User=assistant
WorkingDirectory=/opt/assistant/starter
ExecStart=/opt/assistant/starter/.venv/bin/python brief.py

# assistant-brief.timer
[Timer]
OnCalendar=*-*-* 07:30:00
Persistent=true
[Install]
WantedBy=timers.target
```

   `systemctl enable --now assistant-brief.timer`. Check the timezone with `timedatectl`; the timer uses
   the server's local time.

6. Add a test: an `Agent(read_only=True)` with an ACT tool in the registry offers only READ tools.
   (`test_read_only_agent_never_offers_act_tools` already shows the pattern.)

## Done when

- `cd starter && .venv/bin/python brief.py` delivers one message.
- `systemctl list-timers | grep assistant-brief` shows the next run.
- The next morning it arrived without you doing anything.

## Notes

- If the brief fails (API down), nothing arrives and you may not notice. Have the alarm script check that
  the brief ran (for example, `brief.py` touches a file; the alarm checks its age).
- Keep the brief short. A brief you do not read is noise.
