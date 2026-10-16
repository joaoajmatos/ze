"""POST /eval/confirm answers the eval thread's open confirmation (phase 181, T058)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_agents.park import ParkedLoop, ParkedSubtask, ParkedWrite
from ze_agents.types import AgentResult, ToolCall
from ze_api.api.routes.eval import router

KEY = "k"


def _turn(**overrides) -> SimpleNamespace:
    base = dict(
        final_state={},
        config={},
        interrupted=False,
        confirmation=None,
        error=None,
        response=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _app(resume_result, invoke_result=None) -> tuple[FastAPI, SimpleNamespace]:
    container = SimpleNamespace(
        _build_config=lambda thread_id: {"configurable": {"thread_id": thread_id}},
        resume_turn=AsyncMock(return_value=resume_result),
        invoke_raw_turn=AsyncMock(return_value=invoke_result),
    )
    app = FastAPI()
    app.state.settings = SimpleNamespace(ze_api_key=KEY, eval_mode=True)
    app.state.container = container
    app.include_router(router)
    return app, container


async def _post(app: FastAPI, path: str, body: dict, key: str = KEY):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(path, json=body, headers={"x-ze-api-key": key})


def _executed_delete() -> AgentResult:
    return AgentResult(
        agent="calendar",
        response="Done: deleted the event.",
        tool_calls=[
            ToolCall(
                tool_name="delete_event",
                args={"event_id": "e1"},
                result={"ok": True},
                duration_ms=3,
                success=True,
                gate="approved",
            )
        ],
    )


async def test_approve_resumes_the_eval_thread_and_reports_the_executed_call():
    final = {
        "final_response": "Done: deleted the event.",
        "agent_result": _executed_delete(),
    }
    app, container = _app(_turn(final_state=final, response="Done: deleted the event."))

    resp = await _post(app, "/eval/confirm", {"session_id": "s1", "choice": "approve"})

    assert resp.status_code == 200
    config = container.resume_turn.await_args.args[0]
    assert config["configurable"]["thread_id"] == "eval-s1"
    assert container.resume_turn.await_args.kwargs["resume"] == {
        "choice": "approve",
        "edits": {},
    }
    body = resp.json()
    assert body["session_id"] == "s1"
    assert body["response"] == "Done: deleted the event."
    assert body["pending_confirmation"] is False
    assert body["tool_calls"][0]["tool_name"] == "delete_event"
    assert body["tool_calls"][0]["gate"] == "approved"
    assert body["tool_calls"][0]["parked"] is False


async def test_deny_passes_the_choice_and_edits_through():
    app, container = _app(_turn(final_state={"final_response": "Okay, I didn't."}))

    resp = await _post(
        app,
        "/eval/confirm",
        {"session_id": "s1", "choice": "deny", "edits": {"i1": "new body"}},
    )

    assert resp.status_code == 200
    assert container.resume_turn.await_args.kwargs["resume"] == {
        "choice": "deny",
        "edits": {"i1": "new body"},
    }
    assert resp.json()["response"] == "Okay, I didn't."


def _parked_write(tool: str, args: dict, agent: str) -> ParkedWrite:
    return ParkedWrite(
        item_id=f"item-{tool}",
        call_id=f"call-{tool}",
        tool=tool,
        args=args,
        effect_phrase=tool,
        summary="",
        agent=agent,
    )


def _parked_state(loop: ParkedLoop) -> dict:
    return {"parked_subtasks": [ParkedSubtask(index=0, loop=loop)]}


async def test_a_resume_that_parks_again_reports_a_pending_confirmation():
    loop = ParkedLoop(
        agent="messenger",
        messages=[],
        accumulated=[],
        iteration=1,
        parked=[_parked_write("send_email", {"to": "ana@example.com"}, "messenger")],
    )
    app, _ = _app(_turn(final_state=_parked_state(loop), interrupted=True))

    resp = await _post(app, "/eval/confirm", {"session_id": "s1", "choice": "approve"})

    body = resp.json()
    assert body["pending_confirmation"] is True
    assert body["tool_calls"] == [
        {
            "tool_name": "send_email",
            "args": {"to": "ana@example.com"},
            "duration_ms": 0,
            "success": False,
            "error": None,
            "gate": "parked",
            "parked": True,
        }
    ]


async def test_no_open_confirmation_is_a_conflict():
    app, _ = _app(_turn(error="No pending confirmation."))

    resp = await _post(app, "/eval/confirm", {"session_id": "s1", "choice": "approve"})

    assert resp.status_code == 409


async def test_invalid_choice_is_rejected_before_resuming():
    app, container = _app(_turn())

    resp = await _post(app, "/eval/confirm", {"session_id": "s1", "choice": "maybe"})

    assert resp.status_code == 422
    container.resume_turn.assert_not_awaited()


async def test_wrong_api_key_is_refused():
    app, container = _app(_turn())

    resp = await _post(
        app, "/eval/confirm", {"session_id": "s1", "choice": "approve"}, key="nope"
    )

    assert resp.status_code == 401
    container.resume_turn.assert_not_awaited()


async def test_eval_chat_reports_the_calls_of_a_parked_loop():
    ran = ToolCall(
        tool_name="list_events",
        args={"day": "today"},
        result=[],
        duration_ms=4,
        success=True,
    )
    loop = ParkedLoop(
        agent="calendar",
        messages=[],
        accumulated=[ran],
        iteration=1,
        parked=[_parked_write("delete_event", {"event_id": "e1"}, "calendar")],
    )
    app, _ = _app(
        _turn(),
        invoke_result=_turn(final_state=_parked_state(loop), interrupted=True),
    )

    resp = await _post(
        app, "/eval/chat", {"prompt": "delete my 3pm", "session_id": "s1"}
    )

    body = resp.json()
    assert body["pending_confirmation"] is True
    assert [(c["tool_name"], c["gate"], c["parked"]) for c in body["tool_calls"]] == [
        ("list_events", "none", False),
        ("delete_event", "parked", True),
    ]


async def test_eval_chat_reports_a_conductor_parked_behind_its_delegate():
    research = ToolCall(
        tool_name="delegate_to_agent",
        args={"agent": "research", "task": "Python 3.13 notes"},
        result="notes",
        duration_ms=9,
        success=True,
    )
    child = ParkedLoop(
        agent="messenger",
        messages=[],
        accumulated=[],
        iteration=1,
        parked=[_parked_write("send_email", {"to": "alex@example.com"}, "messenger")],
    )
    conductor = ParkedLoop(
        agent="companion",
        messages=[],
        accumulated=[research],
        iteration=2,
        child=child,
        child_call_id="c2",
        child_arguments={"agent": "messenger", "task": "email Alex"},
    )
    app, _ = _app(
        _turn(),
        invoke_result=_turn(final_state=_parked_state(conductor), interrupted=True),
    )

    resp = await _post(
        app, "/eval/chat", {"prompt": "research and email", "session_id": "s1"}
    )

    calls = [
        (c["tool_name"], c["args"].get("agent"), c["gate"])
        for c in resp.json()["tool_calls"]
    ]
    assert calls == [
        ("delegate_to_agent", "research", "none"),
        ("delegate_to_agent", "messenger", "parked"),
        ("send_email", None, "parked"),
    ]
