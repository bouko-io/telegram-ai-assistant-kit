"""Tools Claude may call.

Two kinds:
- READ: looks, changes nothing. Runs at once.
- ACT: changes something. Proposed with Approve / Decline buttons, runs only after a tap.

When in doubt, a tool is ACT.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

READ = "read"
ACT = "act"


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict
    kind: str  # READ or ACT
    run: Callable[[dict], str]
    # One plain line shown on the approval message, e.g. "Restart service nginx".
    describe: Callable[[dict], str] = lambda args: str(args)

    def schema(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema}


def _disk_usage(args: dict) -> str:
    path = args.get("path") or "/"
    u = shutil.disk_usage(path)
    gb = 1024**3
    return f"{path}: {u.used / gb:.1f} GB used of {u.total / gb:.1f} GB ({u.used / u.total:.0%}), {u.free / gb:.1f} GB free"


def _uptime(_args: dict) -> str:
    try:
        seconds = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return "uptime is not available on this system (no /proc/uptime)"
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    try:
        load = Path("/proc/loadavg").read_text().split()[:3]
        load_txt = f", load average {' '.join(load)}"
    except OSError:
        load_txt = ""
    return f"up {days} d {hours} h {rem // 60} min{load_txt}"


_SERVICE_NAME = re.compile(r"^[A-Za-z0-9@._-]{1,64}$")


def make_restart_service(allowed: tuple[str, ...], dry_run: bool, runner=subprocess.run) -> Callable[[dict], str]:
    def restart(args: dict) -> str:
        name = str(args.get("service", ""))
        # Two checks: a strict name pattern, then the allowlist. The model never
        # chooses a command, only a name from a list you wrote.
        if not _SERVICE_NAME.match(name) or name not in allowed:
            raise ValueError(f"service {name!r} is not in ALLOWED_SERVICES {list(allowed)}")
        cmd = ["systemctl", "restart", name]
        if dry_run:
            return f"DRY RUN (ACT_DRY_RUN=true): would run {' '.join(cmd)}"
        # No shell, fixed argv, timeout. The bot user needs permission for this
        # exact command (for example a sudoers line for this one unit).
        done = runner(cmd, capture_output=True, text=True, timeout=60)
        if done.returncode != 0:
            raise RuntimeError(f"{' '.join(cmd)} failed ({done.returncode}): {done.stderr.strip()[:500]}")
        return f"ran {' '.join(cmd)}: ok"

    return restart


def build_tools(allowed_services: tuple[str, ...] = (), dry_run: bool = True) -> dict[str, Tool]:
    tools = [
        Tool(
            name="disk_usage",
            description="Show used and free disk space for a path on this server. Read-only.",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Mount point or folder, default /"}},
            },
            kind=READ,
            run=_disk_usage,
        ),
        Tool(
            name="uptime",
            description="Show how long this server has been up and its load average. Read-only.",
            input_schema={"type": "object", "properties": {}},
            kind=READ,
            run=_uptime,
        ),
        Tool(
            name="restart_service",
            description=(
                "Restart a systemd service on this server. Changes the server, so the user must approve it. "
                f"Allowed services: {', '.join(allowed_services) or 'none configured'}."
            ),
            input_schema={
                "type": "object",
                "properties": {"service": {"type": "string", "enum": list(allowed_services) or [""]}},
                "required": ["service"],
            },
            kind=ACT,
            run=make_restart_service(allowed_services, dry_run),
            describe=lambda a: f"Restart service {a.get('service')}" + (" (dry run)" if dry_run else ""),
        ),
    ]
    return {t.name: t for t in tools}
