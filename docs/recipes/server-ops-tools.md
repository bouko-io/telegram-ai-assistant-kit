# Recipe: server ops tools with an allowlist

Give Claude useful eyes and a few hands on the server, without a free shell.

## Pattern

- One tool per job. The model chooses from names, never writes commands.
- Arguments are enums or match a strict pattern AND are checked against an allowlist in code.
- `subprocess.run([...], timeout=..., capture_output=True, text=True)`. No `shell=True`.
- Output trimmed (last 40 lines, 2000 characters) so it fits a reply and does not flood the context.
- ACT tools: dry run by default, `describe()` gives one clear line for the approval message.

## Examples to add

READ:

```python
def _service_status(args):
    name = args["service"]
    if name not in ALLOWED:  # same allowlist as restart
        raise ValueError(f"{name} is not allowed")
    out = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True, timeout=10)
    return f"{name}: {out.stdout.strip() or out.stderr.strip()}"

def _recent_logs(args):
    name = args["service"]
    if name not in ALLOWED:
        raise ValueError(f"{name} is not allowed")
    out = subprocess.run(["journalctl", "-u", name, "-n", "40", "--no-pager"],
                         capture_output=True, text=True, timeout=15)
    return out.stdout[-2000:]
```

Logs can contain text written by others (web requests, emails). Treat it as data: it may try to steer
Claude. That is fine as long as it can only lead to an ACT proposal you decline.

ACT: copy `make_restart_service` in `tools.py` for `reload`, or for a fixed script such as
`/opt/assistant/scripts/clear-cache.sh` with no arguments at all.

## Permissions for the bot user

Run the bot as its own user (`assistant`). Allow exactly the commands it needs:

```bash
sudo visudo -f /etc/sudoers.d/assistant
# assistant ALL=(root) NOPASSWD: /usr/bin/systemctl restart web, /usr/bin/systemctl restart worker
```

Then change the argv in the tool to `["sudo", "-n", "systemctl", "restart", name]`. `-n` makes sudo fail
instead of waiting for a password. Check the path with `command -v systemctl`.

## Running the bot as a service

```ini
# /etc/systemd/system/assistant.service
[Unit]
Description=Telegram AI assistant
After=network-online.target
Wants=network-online.target

[Service]
User=assistant
WorkingDirectory=/opt/assistant/starter
ExecStart=/opt/assistant/starter/.venv/bin/python bot.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`sudo systemctl enable --now assistant`, logs with `journalctl -u assistant -f`.

## Tests to write for each tool

- READ: runs with a fake runner, output trimmed.
- ACT: name outside the allowlist raises; dry run returns "DRY RUN"; real run uses the exact argv.
- Agent level: the tool is ACT, so `handle_text` returns buttons and the runner was not called.

## Done when

- `make check` passes with the new tests.
- From the phone: "is web running?" answers from `systemctl`; "restart web" shows buttons;
  "restart sshd" is refused because it is not allowlisted.
