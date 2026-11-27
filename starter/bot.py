"""Main loop: long-poll Telegram, check the allowlist, hand text to the agent.

Run:  python bot.py      (reads settings from the environment or a .env file)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from agent import Agent, Reply, parse_callback
from config import Config, load_config
from telegram import TelegramClient, TelegramError
from tools import build_tools

log = logging.getLogger("bot")

# Bots can download at most 20 MB (docs read 2026-11-27). Check before downloading.
MAX_DOWNLOAD = 20 * 1024 * 1024


def _send(tg, chat_id: int, replies: list[Reply]) -> None:
    for r in replies:
        tg.send_message(chat_id, r.text, reply_markup=r.markup())


def handle_update(update: dict, tg, agent: Agent, allowed: frozenset[int], transcriber=None) -> None:
    if "callback_query" in update:
        cq = update["callback_query"]
        # Always answer the callback, even for strangers, or the button spins.
        if cq["from"]["id"] not in allowed:
            tg.answer_callback(cq["id"], "Not allowed.")
            log.warning("ignored callback from user id %s", cq["from"]["id"])
            return
        tg.answer_callback(cq["id"])
        parsed = parse_callback(cq.get("data") or "")
        msg = cq.get("message")
        if parsed is None or msg is None:
            return
        status, replies = agent.decide(*parsed)
        chat_id = msg["chat"]["id"]
        tg.edit_message(chat_id, msg["message_id"], f"{msg.get('text', '')}\n\n-> {status}")
        _send(tg, chat_id, replies)
        return

    msg = update.get("message")
    if not msg or "from" not in msg:
        return
    user_id, chat_id = msg["from"]["id"], msg["chat"]["id"]
    if user_id not in allowed:
        # Say nothing to strangers. The log line is how you find your own id at setup.
        log.warning("ignored message from user id %s", user_id)
        return

    text = msg.get("text")
    if text is None and "voice" in msg:
        if transcriber is None:
            tg.send_message(chat_id, "Voice notes are off. See docs/recipes/voice-notes.md.")
            return
        voice = msg["voice"]
        if (voice.get("file_size") or 0) > MAX_DOWNLOAD:
            tg.send_message(chat_id, "That voice note is over 20 MB, too big for a bot to download.")
            return
        audio = tg.download_file(tg.get_file(voice["file_id"]))
        text = transcriber.transcribe(audio)
        # Echo what was heard so you can catch a bad transcription before acting on it.
        tg.send_message(chat_id, f"Heard: {text or '(nothing)'}")
        if not text:
            return
    if not text:
        return
    if text.strip() == "/start":
        tg.send_message(chat_id, f"Ready. Send a message or a voice note. (This chat id: {chat_id})")
        return
    _send(tg, chat_id, agent.handle_text(chat_id, text))


def build(config: Config):
    import anthropic

    from voice import make_transcriber

    tg = TelegramClient(config.telegram_token)
    system = Path(config.system_prompt_file).read_text() if config.system_prompt_file else None
    agent = Agent(
        client=anthropic.Anthropic(),  # reads ANTHROPIC_API_KEY; retries 408/409/429/5xx twice by default
        tools=build_tools(config.allowed_services, config.act_dry_run),
        state_dir=config.state_dir,
        model=config.model,
        effort=config.effort,
        use_fallbacks=config.use_fallbacks,
        max_tool_rounds=config.max_tool_rounds,
        **({"system_prompt": system} if system else {}),
    )
    return tg, agent, make_transcriber(config.whisper_model)


def run() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # httpx logs every request URL at INFO, and Telegram URLs contain the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config = load_config()
    tg, agent, transcriber = build(config)
    log.info("started; model=%s dry_run=%s allowed users=%d", config.model, config.act_dry_run, len(config.allowed_user_ids))
    offset = None
    while True:
        try:
            updates = tg.get_updates(offset=offset, timeout=50)
        except TelegramError as e:
            log.error("getUpdates failed: %s", e)
            time.sleep(e.retry_after or 5)
            continue
        except Exception as e:  # network down, DNS, ...
            log.error("getUpdates error: %s", e)
            time.sleep(5)
            continue
        for update in updates:
            offset = update["update_id"] + 1  # confirm on the next call, even if handling fails
            try:
                handle_update(update, tg, agent, config.allowed_user_ids, transcriber)
            except Exception as e:
                log.exception("update %s failed", update.get("update_id"))
                chat = (update.get("message") or {}).get("chat") or ((update.get("callback_query") or {}).get("message") or {}).get("chat")
                sender = (update.get("message") or update.get("callback_query") or {}).get("from", {}).get("id")
                if chat and sender in config.allowed_user_ids:
                    try:
                        tg.send_message(chat["id"], f"Error: {type(e).__name__}: {str(e)[:300]}")
                    except Exception:
                        pass


if __name__ == "__main__":
    run()
