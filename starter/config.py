"""Settings, read from environment variables only. No secrets in code."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    pass


def _int_set(raw: str) -> frozenset[int]:
    out = set()
    for part in raw.replace(" ", "").split(","):
        if part:
            # Telegram user ids are integers up to 52 bits (docs read 2026-11-27).
            out.add(int(part))
    return frozenset(out)


def _bool(raw: str | None, default: bool) -> bool:
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    telegram_token: str
    allowed_user_ids: frozenset[int]
    model: str = "claude-opus-5-5"
    effort: str = "medium"
    use_fallbacks: bool = True
    state_dir: Path = Path("state")
    act_dry_run: bool = True
    allowed_services: tuple[str, ...] = ()
    max_tool_rounds: int = 8
    system_prompt_file: str = ""
    whisper_model: str = ""


def load_config(env: dict | None = None) -> Config:
    env = os.environ if env is None else env
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise ConfigError("TELEGRAM_BOT_TOKEN is not set (see .env.example)")
    users = _int_set(env.get("ALLOWED_USER_IDS", ""))
    if not users:
        # Fail closed: a bot with an empty allowlist would answer nobody, which is
        # safe, but it is almost always a setup mistake, so stop loudly.
        raise ConfigError("ALLOWED_USER_IDS is empty. Put your own Telegram user id there.")
    model = env.get("MODEL", "claude-opus-5-5")
    services = tuple(s for s in env.get("ALLOWED_SERVICES", "").replace(" ", "").split(",") if s)
    return Config(
        telegram_token=token,
        allowed_user_ids=users,
        model=model,
        effort=env.get("EFFORT", "medium"),
        # Server-side fallbacks are recommended for claude-opus-5-5 (verified 2026-11-27).
        use_fallbacks=_bool(env.get("USE_FALLBACKS"), default=model == "claude-opus-5-5"),
        state_dir=Path(env.get("STATE_DIR", "state")),
        act_dry_run=_bool(env.get("ACT_DRY_RUN"), default=True),
        allowed_services=services,
        max_tool_rounds=int(env.get("MAX_TOOL_ROUNDS", "8")),
        system_prompt_file=env.get("SYSTEM_PROMPT_FILE", ""),
        whisper_model=env.get("WHISPER_MODEL", ""),
    )
