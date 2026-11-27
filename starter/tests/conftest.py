"""Fakes: no network, no keys. A scripted Claude and a recording Telegram."""

import copy
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import Agent  # noqa: E402
from tools import ACT, READ, Tool  # noqa: E402


@dataclass
class Block:
    type: str
    text: str | None = None
    id: str | None = None
    name: str | None = None
    input: dict | None = None

    def model_dump(self, mode="json", exclude_none=True):
        return {k: v for k, v in self.__dict__.items() if v is not None}


def text(t):
    return Block(type="text", text=t)


def tool_use(tid, name, args=None):
    return Block(type="tool_use", id=tid, name=name, input=args or {})


@dataclass
class Resp:
    content: list
    stop_reason: str


class _Endpoint:
    def __init__(self, owner):
        self.owner = owner

    def create(self, **kwargs):
        self.owner.calls.append(copy.deepcopy(kwargs))
        if not self.owner.script:
            raise AssertionError("fake Claude ran out of scripted responses")
        return self.owner.script.pop(0)


class FakeClaude:
    """Mimics anthropic.Anthropic(): .messages.create and .beta.messages.create."""

    def __init__(self, script=None):
        self.script = list(script or [])
        self.calls = []
        self.messages = _Endpoint(self)
        self.beta = type("B", (), {})()
        self.beta.messages = _Endpoint(self)


@dataclass
class FakeTelegram:
    sent: list = field(default_factory=list)
    answered: list = field(default_factory=list)
    edited: list = field(default_factory=list)
    files: dict = field(default_factory=dict)

    def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})

    def answer_callback(self, cq_id, text=None):
        self.answered.append(cq_id)

    def edit_message(self, chat_id, message_id, text):
        self.edited.append({"chat_id": chat_id, "message_id": message_id, "text": text})

    def get_file(self, file_id):
        return f"voice/{file_id}.oga"

    def download_file(self, path):
        return b"fake-audio"


class Recorder:
    def __init__(self, result="done"):
        self.calls = []
        self.result = result

    def __call__(self, args):
        self.calls.append(args)
        return self.result


@pytest.fixture
def act_spy():
    return Recorder("restarted web")


@pytest.fixture
def tools(act_spy):
    return {
        "uptime": Tool("uptime", "up", {"type": "object", "properties": {}}, READ, lambda a: "up 3 d"),
        "restart_service": Tool(
            "restart_service",
            "restart",
            {"type": "object", "properties": {"service": {"type": "string"}}},
            ACT,
            act_spy,
            describe=lambda a: f"Restart service {a.get('service')}",
        ),
    }


@pytest.fixture
def make_agent(tmp_path, tools):
    def _make(script, **kw):
        claude = FakeClaude(script)
        return Agent(client=claude, tools=tools, state_dir=tmp_path, **kw), claude

    return _make


OWNER = 111
STRANGER = 999


def msg_update(uid, text_=None, voice=None, update_id=1):
    m = {"message_id": 10, "from": {"id": uid}, "chat": {"id": uid}}
    if text_ is not None:
        m["text"] = text_
    if voice is not None:
        m["voice"] = voice
    return {"update_id": update_id, "message": m}


def cb_update(uid, data, text_="Claude wants to: ...", update_id=2):
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"cq{update_id}",
            "from": {"id": uid},
            "data": data,
            "message": {"message_id": 20, "chat": {"id": uid}, "text": text_},
        },
    }
