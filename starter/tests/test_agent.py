from agent import DECLINED, Agent
from conftest import Resp, text, tool_use


def test_plain_answer_is_returned_and_remembered(make_agent):
    agent, claude = make_agent([Resp([text("Hello.")], "end_turn")])
    replies = agent.handle_text(1, "hi")
    assert [r.text for r in replies] == ["Hello."]
    assert agent.history.get(1)[-1] == {"role": "assistant", "content": "Hello."}


def test_request_shape_follows_model_rules(make_agent):
    agent, claude = make_agent([Resp([text("ok")], "end_turn")])
    agent.handle_text(1, "hi")
    call = claude.calls[0]
    assert call["output_config"] == {"effort": "medium"}
    assert call["cache_control"] == {"type": "ephemeral"}
    assert call["betas"] == ["server-side-fallback-2026-07-01"] and call["fallbacks"] == "default"
    for forbidden in ("temperature", "top_p", "thinking", "tool_choice"):
        assert forbidden not in call


def test_read_tool_runs_at_once_and_history_is_append_only(make_agent):
    first = Resp([text("checking"), tool_use("t1", "uptime")], "tool_use")
    agent, claude = make_agent([first, Resp([text("Up 3 days.")], "end_turn")])
    replies = agent.handle_text(1, "how long up?")
    assert replies[0].text == "Up 3 days."
    second = claude.calls[1]["messages"]
    # assistant content appended unchanged, then one user message with the tool_result
    assert second[-2]["role"] == "assistant"
    assert [b.type for b in second[-2]["content"]] == ["text", "tool_use"]
    assert second[-1] == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "up 3 d"}],
    }


def test_act_tool_waits_for_approval(make_agent, act_spy):
    agent, claude = make_agent([Resp([tool_use("t1", "restart_service", {"service": "web"})], "tool_use")])
    replies = agent.handle_text(1, "restart web")
    assert act_spy.calls == []  # nothing ran
    assert len(claude.calls) == 1  # loop paused
    assert "Restart service web" in replies[0].text
    labels = [b["text"] for b in replies[0].buttons[0]]
    assert labels == ["Approve", "Decline"]
    assert len(agent.pending.load()) == 1


def test_approve_runs_tool_and_resumes(make_agent, act_spy):
    agent, claude = make_agent(
        [
            Resp([tool_use("t1", "restart_service", {"service": "web"})], "tool_use"),
            Resp([text("Restarted.")], "end_turn"),
        ]
    )
    replies = agent.handle_text(1, "restart web")
    pid = replies[0].buttons[0][0]["callback_data"].split(":")[1]
    status, out = agent.decide(pid, 0, approved=True)
    assert "approved" in status
    assert act_spy.calls == [{"service": "web"}]
    assert out[0].text == "Restarted."
    result = claude.calls[1]["messages"][-1]["content"][0]
    assert result == {"type": "tool_result", "tool_use_id": "t1", "content": "restarted web"}
    assert agent.pending.load() == {}


def test_decline_sends_error_result_and_never_runs(make_agent, act_spy):
    agent, claude = make_agent(
        [
            Resp([tool_use("t1", "restart_service", {"service": "web"})], "tool_use"),
            Resp([text("OK, left it alone.")], "end_turn"),
        ]
    )
    replies = agent.handle_text(1, "restart web")
    pid = replies[0].buttons[0][1]["callback_data"].split(":")[1]
    agent.decide(pid, 0, approved=False)
    assert act_spy.calls == []
    result = claude.calls[1]["messages"][-1]["content"][0]
    assert result["content"] == DECLINED and result["is_error"] is True


def test_double_tap_is_ignored(make_agent, act_spy):
    agent, _ = make_agent(
        [
            Resp([tool_use("t1", "restart_service", {"service": "web"})], "tool_use"),
            Resp([text("done")], "end_turn"),
        ]
    )
    pid = agent.handle_text(1, "restart web")[0].buttons[0][0]["callback_data"].split(":")[1]
    agent.decide(pid, 0, True)
    status, out = agent.decide(pid, 0, True)
    assert out == [] and "expired" in status
    assert len(act_spy.calls) == 1


def test_mixed_read_and_two_acts_send_all_results_in_one_message(make_agent, act_spy):
    agent, claude = make_agent(
        [
            Resp(
                [
                    tool_use("r1", "uptime"),
                    tool_use("a1", "restart_service", {"service": "web"}),
                    tool_use("a2", "restart_service", {"service": "db"}),
                ],
                "tool_use",
            ),
            Resp([text("done")], "end_turn"),
        ]
    )
    replies = agent.handle_text(1, "restart both")
    assert len(replies) == 2
    pid = replies[0].buttons[0][0]["callback_data"].split(":")[1]
    _, out = agent.decide(pid, 0, True)
    assert out == []  # still waiting for the second button
    _, out = agent.decide(pid, 1, False)
    assert out[0].text == "done"
    blocks = claude.calls[1]["messages"][-1]["content"]
    assert [b["tool_use_id"] for b in blocks] == ["r1", "a1", "a2"]
    assert blocks[2]["is_error"] is True
    assert act_spy.calls == [{"service": "web"}]


def test_pending_survives_restart(tmp_path, tools, act_spy):
    from conftest import FakeClaude

    c1 = FakeClaude([Resp([tool_use("t1", "restart_service", {"service": "web"})], "tool_use")])
    a1 = Agent(client=c1, tools=tools, state_dir=tmp_path)
    pid = a1.handle_text(1, "restart web")[0].buttons[0][0]["callback_data"].split(":")[1]

    c2 = FakeClaude([Resp([text("Restarted after reboot.")], "end_turn")])
    a2 = Agent(client=c2, tools=tools, state_dir=tmp_path)  # new process, same state dir
    _, out = a2.decide(pid, 0, True)
    assert out[0].text == "Restarted after reboot."
    assert c2.calls[0]["messages"][-2]["content"][0]["type"] == "tool_use"  # restored from JSON


def test_refusal_is_not_read_as_answer(make_agent):
    agent, _ = make_agent([Resp([text("partial")], "refusal")])
    replies = agent.handle_text(1, "something")
    assert replies[0].text == "Claude declined to answer this request."
    assert agent.history.get(1) == []


def test_unknown_tool_and_crashing_tool_return_errors(make_agent, tools):
    from tools import READ, Tool

    def boom(_):
        raise RuntimeError("disk gone")

    tools["broken"] = Tool("broken", "x", {"type": "object"}, READ, boom)
    agent, claude = make_agent(
        [Resp([tool_use("t1", "nope"), tool_use("t2", "broken")], "tool_use"), Resp([text("sorry")], "end_turn")]
    )
    agent.handle_text(1, "x")
    blocks = claude.calls[1]["messages"][-1]["content"]
    assert all(b["is_error"] for b in blocks)
    assert "disk gone" in blocks[1]["content"]


def test_read_only_agent_never_offers_act_tools(make_agent):
    agent, claude = make_agent([Resp([text("brief")], "end_turn")], read_only=True)
    agent.handle_text(1, "morning brief")
    assert [t["name"] for t in claude.calls[0]["tools"]] == ["uptime"]


def test_tool_round_limit(make_agent):
    loop = [Resp([tool_use(f"t{i}", "uptime")], "tool_use") for i in range(3)]
    agent, _ = make_agent(loop, max_tool_rounds=3)
    assert "Stopped after 3" in agent.handle_text(1, "x")[0].text


def test_real_sdk_builds_the_request_offline(tmp_path):
    """The real anthropic SDK with a mock transport: checks the JSON body it would send. No network."""
    import json

    import anthropic
    import pytest

    httpx2 = pytest.importorskip("httpx2")  # the HTTP library anthropic 2.x uses internally
    from tools import build_tools

    seen = {}

    def handler(request):
        seen["beta"] = request.headers.get("anthropic-beta")
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={
            "id": "m1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn",
            "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
        })

    client = anthropic.Anthropic(api_key="offline", http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
    agent = Agent(client=client, tools=build_tools(("web",)), state_dir=tmp_path)
    assert agent.handle_text(1, "hi")[0].text == "ok"
    body = seen["body"]
    assert seen["beta"] == "server-side-fallback-2026-07-01"
    assert body["fallbacks"] == "default" and body["output_config"] == {"effort": "medium"}
    assert body["cache_control"] == {"type": "ephemeral"}
    assert {t["name"] for t in body["tools"]} == {"disk_usage", "uptime", "restart_service"}
