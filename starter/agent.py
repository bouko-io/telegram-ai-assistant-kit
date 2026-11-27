"""The agent loop: Claude + tools + approval.

A manual tool loop (not the SDK tool runner) because an ACT tool waits for a
human tap that may come minutes later. We persist the pending state (messages +
tool_use ids) to a JSON file and resume the loop when the tap arrives.

Anthropic API facts used here (verified 2026-11-27, SDK tested: anthropic 2.14.0):
- Append the assistant content UNCHANGED (it may hold thinking blocks); history is append-only.
- Then ONE user message with ALL tool_result blocks for that turn.
- stop_reason: end_turn, tool_use, max_tokens, pause_turn, refusal, stop_sequence.
- claude-opus-5-5: no temperature/top_p, no "thinking disabled", no forced tool_choice.
- Keep system prompt and tool list byte-stable (no timestamps) so prompt caching hits.
"""

from __future__ import annotations

import json
import os
import secrets
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from telegram import button
from tools import ACT, READ, Tool

DECLINED = "The user declined this action."
DEFAULT_SYSTEM = (
    "You are a private assistant on Telegram for one person who runs their own server. "
    "Answer briefly in plain text (no Markdown), in the language the user writes in. "
    "Use read tools freely. Tools that change something need the user's approval: the app asks them, "
    "you just call the tool. If an action was declined, do not retry it; say what you would need."
)
HISTORY_LIMIT = 20  # messages kept per chat (plain text only, see HistoryStore)


@dataclass
class Reply:
    text: str
    buttons: list[list[dict]] | None = None

    def markup(self) -> dict | None:
        return {"inline_keyboard": self.buttons} if self.buttons else None


def _plain(value):
    """Turn SDK objects into JSON-safe dicts for the pending file."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def _get(block, key, default=None):
    return block.get(key, default) if isinstance(block, dict) else getattr(block, key, default)


class JsonStore:
    """One JSON file, written atomically. Small and boring on purpose."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text())

    def save(self, data: dict) -> None:
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        os.replace(tmp, self.path)
        os.chmod(self.path, 0o600)


class HistoryStore(JsonStore):
    """Per-chat memory of finished exchanges as plain text.

    Only the user's text and Claude's final answer are kept, never tool blocks,
    so trimming old turns can never split a tool_use from its tool_result.
    """

    def get(self, chat_id: int) -> list[dict]:
        return self.load().get(str(chat_id), [])

    def add(self, chat_id: int, user_text: str, answer: str) -> None:
        data = self.load()
        hist = data.get(str(chat_id), [])
        hist += [{"role": "user", "content": user_text}, {"role": "assistant", "content": answer}]
        data[str(chat_id)] = hist[-HISTORY_LIMIT:]
        self.save(data)


@dataclass
class Agent:
    client: object  # anthropic.Anthropic() or a fake with the same .messages / .beta.messages
    tools: dict[str, Tool]
    state_dir: Path
    model: str = "claude-opus-5-5"
    effort: str = "medium"
    use_fallbacks: bool = True
    system_prompt: str = DEFAULT_SYSTEM
    max_tool_rounds: int = 8
    read_only: bool = False  # True for the morning brief: ACT tools are not even offered
    pending: JsonStore = field(init=False)
    history: HistoryStore = field(init=False)

    def __post_init__(self):
        self.state_dir = Path(self.state_dir)
        self.pending = JsonStore(self.state_dir / "pending.json")
        self.history = HistoryStore(self.state_dir / "history.json")
        if self.read_only:
            self.tools = {n: t for n, t in self.tools.items() if t.kind == READ}

    # ---- model call -------------------------------------------------------

    def _create(self, messages: list):
        kwargs = dict(
            model=self.model,
            max_tokens=16000,  # fine for non-streaming calls
            system=self.system_prompt,
            tools=[t.schema() for t in self.tools.values()],
            messages=messages,
            # Opus 5.5 always thinks; effort is how hard. Set it explicitly.
            output_config={"effort": self.effort},
            # Auto-caches the last cacheable block. Check usage.cache_read_input_tokens.
            cache_control={"type": "ephemeral"},
        )
        if self.use_fallbacks:
            return self.client.beta.messages.create(
                **kwargs, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
            )
        return self.client.messages.create(**kwargs)

    # ---- public entry points ---------------------------------------------

    def handle_text(self, chat_id: int, text: str) -> list[Reply]:
        messages = self.history.get(chat_id) + [{"role": "user", "content": text}]
        return self._run(chat_id, text, messages, rounds=0)

    def decide(self, pending_id: str, index: int, approved: bool) -> tuple[str, list[Reply]]:
        """Record one tap. Returns (new text for the approval message, replies to send)."""
        all_pending = self.pending.load()
        p = all_pending.get(pending_id)
        if p is None or not 0 <= index < len(p["acts"]):
            return "This request has expired or was already handled.", []
        act = p["acts"][index]
        if act["decision"] is not None:
            return f"{act['label']}: already {act['decision']}.", []
        act["decision"] = "approved" if approved else "declined"
        status = f"{act['label']}: {act['decision']}."

        if any(a["decision"] is None for a in p["acts"]):
            self.pending.save(all_pending)  # still waiting on another button
            return status, []

        del all_pending[pending_id]
        self.pending.save(all_pending)
        results = dict(p["results"])
        for a in p["acts"]:
            if a["decision"] == "approved":
                results[a["id"]] = self._run_tool(a["name"], a["input"])
            else:
                results[a["id"]] = {"content": DECLINED, "is_error": True}
        messages = p["messages"] + [self._results_message(p["order"], results)]
        return status, self._run(p["chat_id"], p["user_text"], messages, rounds=p["rounds"] + 1)

    # ---- loop ---------------------------------------------------------------

    def _run(self, chat_id: int, user_text: str, messages: list, rounds: int) -> list[Reply]:
        while True:
            if rounds >= self.max_tool_rounds:
                return [Reply(f"Stopped after {rounds} tool rounds without a final answer.")]
            resp = self._create(messages)
            stop = resp.stop_reason
            if stop == "refusal":
                # Do not read the content as an answer.
                return [Reply("Claude declined to answer this request.")]
            messages.append({"role": "assistant", "content": resp.content})  # unchanged
            if stop == "pause_turn":
                rounds += 1
                continue  # server-side work paused; send the conversation back as is
            if stop != "tool_use":
                text = "\n".join(_get(b, "text", "") for b in resp.content if _get(b, "type") == "text").strip()
                if stop == "max_tokens":
                    text += "\n\n(answer cut off: max_tokens reached)"
                text = text or "(no text in reply)"
                self.history.add(chat_id, user_text, text)
                return [Reply(text)]

            order, results, acts = [], {}, []
            for b in resp.content:
                if _get(b, "type") != "tool_use":
                    continue
                tid, name, args = _get(b, "id"), _get(b, "name"), _get(b, "input") or {}
                order.append(tid)
                tool = self.tools.get(name)
                if tool is None:
                    results[tid] = {"content": f"Unknown tool {name!r}.", "is_error": True}
                elif tool.kind == ACT:
                    acts.append({"id": tid, "name": name, "input": args, "label": tool.describe(args), "decision": None})
                else:
                    results[tid] = self._run_tool(name, args)

            if acts:
                return self._ask_approval(chat_id, user_text, messages, order, results, acts, rounds)
            messages.append(self._results_message(order, results))
            rounds += 1

    def _run_tool(self, name: str, args: dict) -> dict:
        try:
            return {"content": str(self.tools[name].run(args)), "is_error": False}
        except Exception as e:  # the model sees the error and can adapt
            return {"content": f"{type(e).__name__}: {e}", "is_error": True}

    @staticmethod
    def _results_message(order: list[str], results: dict) -> dict:
        blocks = []
        for tid in order:
            r = results[tid]
            block = {"type": "tool_result", "tool_use_id": tid, "content": r["content"]}
            if r.get("is_error"):
                block["is_error"] = True
            blocks.append(block)
        return {"role": "user", "content": blocks}

    def _ask_approval(self, chat_id, user_text, messages, order, results, acts, rounds) -> list[Reply]:
        pid = secrets.token_hex(4)
        all_pending = self.pending.load()
        all_pending[pid] = {
            "chat_id": chat_id,
            "user_text": user_text,
            "messages": _plain(messages),
            "order": order,
            "results": results,
            "acts": acts,
            "rounds": rounds,
        }
        self.pending.save(all_pending)
        replies = []
        for i, a in enumerate(acts):
            # "a:<8 hex>:<n>" is about 12 bytes, well under the 64-byte limit.
            replies.append(
                Reply(
                    f"Claude wants to: {a['label']}\nInput: {json.dumps(a['input'], ensure_ascii=False)}",
                    buttons=[[button("Approve", f"a:{pid}:{i}"), button("Decline", f"d:{pid}:{i}")]],
                )
            )
        return replies


def parse_callback(data: str) -> tuple[str, int, bool] | None:
    try:
        verb, pid, idx = data.split(":")
        if verb not in ("a", "d"):
            return None
        return pid, int(idx), verb == "a"
    except ValueError:
        return None
