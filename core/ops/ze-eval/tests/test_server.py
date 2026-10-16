import asyncio
import json

from ze_eval import server


def test_scenario_confirm_turns_call_eval_confirm_for_the_same_session(monkeypatch):
    calls: list[tuple] = []

    async def fake_chat(prompt, session_id):
        calls.append(("chat", prompt, session_id))
        return {"agent_used": "calendar", "pending_confirmation": True}

    async def fake_confirm(choice, session_id, edits=None):
        calls.append(("confirm", choice, session_id, edits))
        return {"agent_used": "calendar", "pending_confirmation": False}

    monkeypatch.setattr(server, "_do_chat", fake_chat)
    monkeypatch.setattr(server, "_do_confirm", fake_confirm)
    scenario = {
        "turns": [
            {"prompt": "delete my 3pm"},
            {"confirm": "approve", "edits": {"item-1": "x"}},
        ]
    }

    result = asyncio.run(server._run_scenario_turns(scenario, "eval-s"))

    assert calls == [
        ("chat", "delete my 3pm", "eval-s"),
        ("confirm", "approve", "eval-s", {"item-1": "x"}),
    ]
    assert [t.get("confirm") for t in result["turns"]] == [None, "approve"]
    assert result["agent_used"] == "calendar"


def test_ze_confirm_returns_the_resumed_turn_as_json(monkeypatch):
    async def fake_confirm(choice, session_id, edits=None):
        return {"response": "Done", "pending_confirmation": False}

    monkeypatch.setattr(server, "_do_confirm", fake_confirm)

    out = asyncio.run(server.ze_confirm("deny", session_id="s"))

    assert json.loads(out)["response"] == "Done"
