"""Tiny Telegram Bot API client. Only the methods this bot needs.

Facts from https://core.telegram.org/bots/api and /bots/faq (docs read 2026-11-27):
- Every response is JSON {"ok": bool, "result" | "description", "error_code"}.
  HTTP status codes for errors are NOT documented, so we trust "ok", not the status.
- Flood control errors may carry parameters.retry_after (seconds).
- Avoid more than ~1 message per second in one chat; bursts get 429.
"""

from __future__ import annotations

import time

import httpx

API = "https://api.telegram.org"

# sendMessage text must be 1-4096 characters after entity parsing (docs read 2026-11-27).
# We send plain text (no parse_mode), so there are no entities to parse.
MAX_TEXT = 4096
# callback_data is 1-64 BYTES (docs read 2026-11-27). Bytes, not characters.
MAX_CALLBACK_BYTES = 64


class TelegramError(RuntimeError):
    def __init__(self, method: str, description: str, error_code: int | None, retry_after: int | None):
        super().__init__(f"{method}: {error_code} {description}")
        self.method = method
        self.description = description
        self.error_code = error_code
        self.retry_after = retry_after


def _utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def split_text(text: str, limit: int = MAX_TEXT) -> list[str]:
    """Split text into chunks Telegram accepts.

    The docs say "characters" without defining them. We count UTF-16 code units,
    which is never fewer than Python characters, so the chunks are safe either way.
    Prefers to cut at a newline, then a space.
    """
    text = text if text.strip() else "(empty reply)"
    chunks: list[str] = []
    while text:
        if _utf16_len(text) <= limit:
            chunks.append(text)
            break
        # Largest prefix that fits.
        end = 0
        units = 0
        for i, ch in enumerate(text):
            units += 2 if ord(ch) > 0xFFFF else 1
            if units > limit:
                break
            end = i + 1
        cut = text.rfind("\n", 0, end)
        if cut < end // 2:
            cut = text.rfind(" ", 0, end)
        if cut < end // 2:
            cut = end
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n ")
    return chunks


def button(text: str, callback_data: str) -> dict:
    if not 1 <= len(callback_data.encode("utf-8")) <= MAX_CALLBACK_BYTES:
        raise ValueError(f"callback_data must be 1-{MAX_CALLBACK_BYTES} bytes: {callback_data!r}")
    return {"text": text, "callback_data": callback_data}


class TelegramClient:
    def __init__(self, token: str, http: httpx.Client | None = None, min_interval: float = 1.0):
        self._base = f"{API}/bot{token}"
        self._file_base = f"{API}/file/bot{token}"
        # Long polling holds the request open for `timeout` seconds; the HTTP
        # timeout must be longer than that.
        self._http = http or httpx.Client(timeout=httpx.Timeout(70.0, connect=10.0))
        self._min_interval = min_interval
        self._last_send: dict[int, float] = {}

    def _call(self, method: str, **params):
        params = {k: v for k, v in params.items() if v is not None}
        resp = self._http.post(f"{self._base}/{method}", json=params)
        try:
            body = resp.json()
        except ValueError:
            raise TelegramError(method, f"non-JSON reply (HTTP {resp.status_code})", resp.status_code, None)
        if not body.get("ok"):
            retry = (body.get("parameters") or {}).get("retry_after")
            raise TelegramError(method, body.get("description", ""), body.get("error_code"), retry)
        return body["result"]

    def _pace(self, chat_id: int) -> None:
        last = self._last_send.get(chat_id, 0.0)
        wait = self._min_interval - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        self._last_send[chat_id] = time.monotonic()

    def get_updates(self, offset: int | None = None, timeout: int = 50) -> list[dict]:
        # offset = last processed update_id + 1 confirms earlier updates.
        # timeout = long-poll seconds (default 0 = short polling).
        # Does not work while a webhook is set: call deleteWebhook once first.
        # Unconfirmed updates are kept at most 24 hours. (docs read 2026-11-27)
        return self._call(
            "getUpdates",
            offset=offset,
            timeout=timeout,
            limit=100,  # 1-100
            allowed_updates=["message", "callback_query"],
        )

    def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> list[dict]:
        sent = []
        chunks = split_text(text)
        for i, chunk in enumerate(chunks):
            self._pace(chat_id)
            markup = reply_markup if i == len(chunks) - 1 else None  # buttons on the last chunk
            sent.append(self._call("sendMessage", chat_id=chat_id, text=chunk, reply_markup=markup))
        return sent

    def answer_callback(self, callback_query_id: str, text: str | None = None) -> None:
        # Must be called for every callback, or the user's client shows a progress bar.
        self._call("answerCallbackQuery", callback_query_id=callback_query_id, text=text)

    def edit_message(self, chat_id: int, message_id: int, text: str) -> None:
        self._call("editMessageText", chat_id=chat_id, message_id=message_id, text=split_text(text)[0])

    def get_file(self, file_id: str) -> str:
        return self._call("getFile", file_id=file_id)["file_path"]

    def download_file(self, file_path: str) -> bytes:
        # Bots can download files up to 20 MB (docs read 2026-11-27).
        resp = self._http.get(f"{self._file_base}/{file_path}")
        if resp.status_code != 200:
            # Not raise_for_status(): its message contains the URL, and the URL contains the token.
            raise TelegramError("downloadFile", f"HTTP {resp.status_code}", resp.status_code, None)
        return resp.content
