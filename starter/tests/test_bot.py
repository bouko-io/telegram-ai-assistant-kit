import pytest

from bot import handle_update
from conftest import OWNER, STRANGER, FakeTelegram, Resp, cb_update, msg_update, text, tool_use

ALLOWED = frozenset({OWNER})


def test_stranger_message_is_ignored_silently(make_agent):
    agent, claude = make_agent([])
    tg = FakeTelegram()
    handle_update(msg_update(STRANGER, "hi"), tg, agent, ALLOWED)
    assert tg.sent == [] and claude.calls == []


def test_stranger_cannot_press_approve(make_agent, act_spy):
    agent, _ = make_agent([Resp([tool_use("t1", "restart_service", {"service": "web"})], "tool_use")])
    tg = FakeTelegram()
    handle_update(msg_update(OWNER, "restart web"), tg, agent, ALLOWED)
    data = tg.sent[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    handle_update(cb_update(STRANGER, data), tg, agent, ALLOWED)
    assert act_spy.calls == []
    assert tg.answered == ["cq2"]  # still answered, so the button stops spinning
    assert len(agent.pending.load()) == 1


def test_owner_tap_runs_and_edits_approval_message(make_agent, act_spy):
    agent, _ = make_agent(
        [
            Resp([tool_use("t1", "restart_service", {"service": "web"})], "tool_use"),
            Resp([text("Restarted.")], "end_turn"),
        ]
    )
    tg = FakeTelegram()
    handle_update(msg_update(OWNER, "restart web"), tg, agent, ALLOWED)
    data = tg.sent[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    handle_update(cb_update(OWNER, data), tg, agent, ALLOWED)
    assert act_spy.calls == [{"service": "web"}]
    assert "approved" in tg.edited[0]["text"]
    assert tg.sent[-1]["text"] == "Restarted."


def test_callback_data_fits_64_bytes(make_agent):
    agent, _ = make_agent([Resp([tool_use("t1", "restart_service", {"service": "web"})], "tool_use")])
    tg = FakeTelegram()
    handle_update(msg_update(OWNER, "restart web"), tg, agent, ALLOWED)
    for row in tg.sent[0]["reply_markup"]["inline_keyboard"]:
        for b in row:
            assert 1 <= len(b["callback_data"].encode()) <= 64


def test_button_helper_rejects_long_callback_data():
    from telegram import button

    with pytest.raises(ValueError):
        button("x", "é" * 33)  # 66 bytes, 33 characters


class FakeTranscriber:
    def transcribe(self, audio):
        assert audio == b"fake-audio"
        return "how is the disk"


def test_voice_note_is_transcribed_echoed_and_answered(make_agent):
    agent, claude = make_agent([Resp([text("Disk is fine.")], "end_turn")])
    tg = FakeTelegram()
    voice = {"file_id": "F1", "file_unique_id": "U1", "duration": 3, "file_size": 1000}
    handle_update(msg_update(OWNER, voice=voice), tg, agent, ALLOWED, FakeTranscriber())
    assert tg.sent[0]["text"] == "Heard: how is the disk"
    assert tg.sent[1]["text"] == "Disk is fine."
    assert claude.calls[0]["messages"][-1]["content"] == "how is the disk"


def test_voice_off_says_so(make_agent):
    agent, claude = make_agent([])
    tg = FakeTelegram()
    handle_update(msg_update(OWNER, voice={"file_id": "F1", "duration": 1}), tg, agent, ALLOWED)
    assert "Voice notes are off" in tg.sent[0]["text"] and claude.calls == []


def test_voice_over_20mb_is_refused(make_agent):
    agent, _ = make_agent([])
    tg = FakeTelegram()
    big = {"file_id": "F1", "duration": 1, "file_size": 21 * 1024 * 1024}
    handle_update(msg_update(OWNER, voice=big), tg, agent, ALLOWED, FakeTranscriber())
    assert "20 MB" in tg.sent[0]["text"]


def test_start_tells_owner_the_chat_id(make_agent):
    agent, claude = make_agent([])
    tg = FakeTelegram()
    handle_update(msg_update(OWNER, "/start"), tg, agent, ALLOWED)
    assert str(OWNER) in tg.sent[0]["text"] and claude.calls == []
