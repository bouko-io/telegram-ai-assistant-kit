import json

import httpx
import pytest

from config import ConfigError, load_config
from telegram import MAX_TEXT, TelegramClient, TelegramError, split_text
from tools import ACT, READ, build_tools, make_restart_service


# ---- message splitting ------------------------------------------------------

def test_short_text_is_one_chunk():
    assert split_text("hello") == ["hello"]


def test_long_text_splits_at_4096_and_keeps_everything():
    words = ("word " * 3000).strip()  # ~15k chars
    chunks = split_text(words)
    assert len(chunks) > 1
    assert all(1 <= len(c) <= MAX_TEXT for c in chunks)
    assert " ".join(chunks).split() == words.split()


def test_split_counts_emoji_as_two_utf16_units():
    s = "\U0001F600" * 3000  # 3000 chars, 6000 UTF-16 units
    chunks = split_text(s)
    assert all(len(c.encode("utf-16-le")) // 2 <= MAX_TEXT for c in chunks)
    assert "".join(chunks) == s


def test_empty_text_is_never_sent_empty():
    assert split_text("   ") == ["(empty reply)"]


# ---- Telegram client: trust "ok", not the HTTP status --------------------------

def _client(handler):
    return TelegramClient("TEST", http=httpx.Client(transport=httpx.MockTransport(handler)), min_interval=0)


def test_ok_false_raises_with_retry_after():
    def handler(request):
        return httpx.Response(
            200, json={"ok": False, "error_code": 429, "description": "Too Many Requests", "parameters": {"retry_after": 7}}
        )

    with pytest.raises(TelegramError) as e:
        _client(handler).send_message(1, "hi")
    assert e.value.retry_after == 7 and e.value.error_code == 429


def test_send_message_posts_plain_text_and_buttons_on_last_chunk():
    seen = []

    def handler(request):
        seen.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": len(seen)}})

    markup = {"inline_keyboard": [[{"text": "Approve", "callback_data": "a:x:0"}]]}
    _client(handler).send_message(5, "x " * 5000, reply_markup=markup)
    assert all(p.endswith("/sendMessage") for p, _ in seen)
    assert "parse_mode" not in seen[0][1]
    assert "reply_markup" not in seen[0][1] and seen[-1][1]["reply_markup"] == markup


def test_get_updates_asks_for_long_poll():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": []})

    _client(handler).get_updates(offset=42, timeout=50)
    assert seen[0]["offset"] == 42 and seen[0]["timeout"] == 50
    assert seen[0]["allowed_updates"] == ["message", "callback_query"]


# ---- tools -------------------------------------------------------------------

def test_tool_kinds():
    t = build_tools(("web",))
    assert t["disk_usage"].kind == READ and t["uptime"].kind == READ
    assert t["restart_service"].kind == ACT


def test_disk_usage_runs_here():
    assert "GB" in build_tools()["disk_usage"].run({"path": "/"})


def test_restart_is_dry_run_by_default():
    out = build_tools(("web",))["restart_service"].run({"service": "web"})
    assert out.startswith("DRY RUN")


def test_restart_refuses_names_outside_allowlist():
    restart = make_restart_service(("web",), dry_run=False, runner=lambda *a, **k: pytest.fail("ran"))
    for bad in ["db", "web; rm -rf /", "../web", ""]:
        with pytest.raises(ValueError):
            restart({"service": bad})


def test_restart_real_run_uses_fixed_argv():
    calls = []

    class Done:
        returncode = 0
        stderr = ""

    def runner(cmd, **kw):
        calls.append((cmd, kw))
        return Done()

    make_restart_service(("web",), dry_run=False, runner=runner)({"service": "web"})
    assert calls[0][0] == ["systemctl", "restart", "web"]
    assert "shell" not in calls[0][1]


# ---- config ------------------------------------------------------------------

def test_config_fails_closed_without_allowlist():
    with pytest.raises(ConfigError):
        load_config({"TELEGRAM_BOT_TOKEN": "x"})


def test_config_defaults_are_safe():
    c = load_config({"TELEGRAM_BOT_TOKEN": "x", "ALLOWED_USER_IDS": "123, 456"})
    assert c.allowed_user_ids == {123, 456}
    assert c.act_dry_run is True and c.model == "claude-opus-5-5" and c.use_fallbacks is True
