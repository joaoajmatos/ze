"""Resuming a parked loop runs exactly the approved calls first (Phase 181, D2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.delegate import DELEGATE_TOOL_NAME
from ze_agents.errors import LoopParked
from ze_agents.park import DECLINED_RESULT, WriteDecision
from ze_agents.registry import agent, clear_registry, register_instance
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext, AgentResult

events: list[tuple] = []


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    events.clear()

    async def list_events() -> str:
        events.append(("tool", "list_events", {}))
        return "events"

    tool(access=ToolAccess.READ, description="list")(list_events)

    async def delete_event(event_id: str = "") -> str:
        events.append(("tool", "delete_event", {"event_id": event_id}))
        return f"deleted {event_id}"

    tool(
        access=ToolAccess.WRITE,
        description="delete",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="deleted a calendar event",
    )(delete_event)

    async def send_email(to: str = "", body: str = "") -> str:
        events.append(("tool", "send_email", {"to": to, "body": body}))
        return "sent"

    tool(
        access=ToolAccess.WRITE,
        description="send",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="sent an email",
        editable_field="body",
    )(send_email)
    yield
    clear_registry()
    clear_tool_registry()


def _client(*responses):
    queue = list(responses)

    async def _complete(**kw):
        events.append(("model", len(kw["messages"])))
        return queue.pop(0)

    client = MagicMock()
    client.complete_with_tools = AsyncMock(side_effect=_complete)
    client.complete = AsyncMock(return_value="fallback")
    return client


def _tc(id_: str, name: str, **args):
    return {"id": id_, "name": name, "arguments": args}


class _Cal(BaseAgent):
    name = "calendar"
    description = "cal"
    tools = ["list_events", "delete_event", "send_email"]

    async def run(self, ctx):  # pragma: no cover
        raise NotImplementedError


def _ctx(**kw) -> AgentContext:
    return AgentContext(session_id="s", prompt="p", **kw)


async def _park(client) -> object:
    with pytest.raises(LoopParked) as info:
        await _Cal().agentic_loop(
            _ctx(), client, [{"role": "user", "content": "go"}], system="s"
        )
    return info.value.loop


def _resume_ctx(loop, *decisions: WriteDecision) -> AgentContext:
    return _ctx(
        resume=loop,
        write_decisions={d.item_id: d for d in decisions},
        write_round=1,
    )


async def test_approved_call_runs_before_any_model_call() -> None:
    loop = await _park(_client((None, [_tc("c1", "delete_event", event_id="e1")])))
    events.clear()
    item = loop.parked[0].item_id
    client = _client(("All done.", None))
    ctx = _resume_ctx(loop, WriteDecision(item, "approved"))
    text, calls = await _Cal().agentic_loop(ctx, client, [], system="s")
    assert text == "All done."
    assert [e[:2] for e in events] == [("tool", "delete_event"), ("model", 3)]
    assert events[0][2] == {"event_id": "e1"}
    assert calls[-1].gate == "approved" and calls[-1].success
    tool_msg = loop.messages[-1] if loop.messages[-1]["role"] == "tool" else None
    assert tool_msg is None  # the saved transcript is not mutated in place


async def test_resumed_transcript_answers_the_original_call_id() -> None:
    loop = await _park(_client((None, [_tc("c1", "delete_event", event_id="e1")])))
    client = _client(("ok", None))
    ctx = _resume_ctx(loop, WriteDecision(loop.parked[0].item_id, "approved"))
    await _Cal().agentic_loop(ctx, client, [], system="s")
    sent = client.complete_with_tools.call_args.kwargs["messages"]
    assert sent[-1] == {
        "role": "tool",
        "tool_call_id": "c1",
        "content": "deleted e1",
    }


async def test_edited_call_changes_only_the_editable_field() -> None:
    loop = await _park(
        _client((None, [_tc("c1", "send_email", to="ana@x.com", body="draft")]))
    )
    events.clear()
    ctx = _resume_ctx(
        loop, WriteDecision(loop.parked[0].item_id, "edited", edited_text="better")
    )
    await _Cal().agentic_loop(ctx, _client(("ok", None)), [], system="s")
    assert events[0] == ("tool", "send_email", {"to": "ana@x.com", "body": "better"})


async def test_denied_call_does_not_run_and_reports_declined() -> None:
    loop = await _park(_client((None, [_tc("c1", "delete_event", event_id="e1")])))
    events.clear()
    client = _client(("Okay.", None))
    ctx = _resume_ctx(loop, WriteDecision(loop.parked[0].item_id, "denied"))
    _, calls = await _Cal().agentic_loop(ctx, client, [], system="s")
    assert [e for e in events if e[0] == "tool"] == []
    assert calls[-1].gate == "denied"
    sent = client.complete_with_tools.call_args.kwargs["messages"]
    assert sent[-1]["content"] == DECLINED_RESULT
    assert sent[-1]["tool_call_id"] == "c1"


async def test_resumed_loop_can_park_again_with_a_new_call() -> None:
    loop = await _park(_client((None, [_tc("c1", "delete_event", event_id="e1")])))
    client = _client((None, [_tc("c2", "send_email", to="a", body="b")]))
    ctx = _resume_ctx(loop, WriteDecision(loop.parked[0].item_id, "approved"))
    with pytest.raises(LoopParked) as info:
        await _Cal().agentic_loop(ctx, client, [], system="s")
    again = info.value.loop
    assert [p.call_id for p in again.parked] == ["c2"]
    assert again.parked[0].item_id != loop.parked[0].item_id
    assert [a.tool_name for a in again.accumulated] == ["delete_event"]


async def test_iteration_counter_continues_after_resume() -> None:
    loop = await _park(
        _client(
            (None, [_tc("c0", "list_events")]),
            (None, [_tc("c1", "delete_event", event_id="e1")]),
        )
    )
    assert loop.iteration == 1
    client = _client((None, [_tc("c2", "send_email", to="a", body="b")]))
    ctx = _resume_ctx(loop, WriteDecision(loop.parked[0].item_id, "approved"))
    with pytest.raises(LoopParked) as info:
        await _Cal().agentic_loop(ctx, client, [], system="s")
    assert info.value.loop.iteration == 2


async def test_model_cannot_change_an_approved_call() -> None:
    loop = await _park(_client((None, [_tc("c1", "delete_event", event_id="e1")])))
    events.clear()
    client = _client((None, [_tc("c9", "delete_event", event_id="e1")]))
    ctx = _resume_ctx(loop, WriteDecision(loop.parked[0].item_id, "approved"))
    with pytest.raises(LoopParked) as info:
        await _Cal().agentic_loop(ctx, client, [], system="s")
    assert [e for e in events if e[0] == "tool"] == [
        ("tool", "delete_event", {"event_id": "e1"})
    ]
    assert info.value.loop.parked[0].call_id == "c9"


class _Companion(BaseAgent):
    name = "companion"
    description = "c"
    tools = ["list_events"]

    async def run(self, ctx):  # pragma: no cover
        raise NotImplementedError


def _register_calendar(client) -> None:
    async def _run(self, ctx: AgentContext) -> AgentResult:
        text, tcs = await self.agentic_loop(
            ctx,
            client,
            list(ctx.messages),
            system="s",
            tool_names=["list_events", "delete_event"],
        )
        return AgentResult(agent=self.name, response=text, tool_calls=tcs)

    cls = type(
        "_CalendarAgent",
        (BaseAgent,),
        {"name": "calendar", "description": "cal", "tools": [], "run": _run},
    )
    agent(cls)
    register_instance("calendar", cls())


def _comp_ctx(**kw) -> AgentContext:
    return _ctx(**kw)


async def test_nested_conductor_resumes_the_specialist_first() -> None:
    spec_client = _client(
        (None, [_tc("k1", "delete_event", event_id="e1")]),
        ("Deleted the 3pm.", None),
    )
    _register_calendar(spec_client)
    comp_client = _client(
        (
            None,
            [
                _tc(
                    "d1",
                    DELEGATE_TOOL_NAME,
                    agent_name="calendar",
                    objective="delete my 3pm",
                )
            ],
        ),
        ("Your 3pm is gone.", None),
    )
    with pytest.raises(LoopParked) as info:
        await _Companion().agentic_loop(
            _comp_ctx(), comp_client, [{"role": "user", "content": "x"}], system="s"
        )
    loop = info.value.loop
    item = loop.all_parked()[0].item_id
    events.clear()

    ctx = _comp_ctx(
        resume=loop,
        write_decisions={item: WriteDecision(item, "approved")},
        write_round=1,
    )
    text, calls = await _Companion().agentic_loop(ctx, comp_client, [], system="s")
    assert text == "Your 3pm is gone."
    assert [e for e in events if e[0] == "tool"] == [
        ("tool", "delete_event", {"event_id": "e1"})
    ]
    sent = comp_client.complete_with_tools.call_args.kwargs["messages"]
    assert sent[-1]["tool_call_id"] == "d1"
    assert "Deleted the 3pm." in sent[-1]["content"]
    assert calls[-1].tool_name == DELEGATE_TOOL_NAME


async def test_nested_specialist_can_re_park_the_conductor() -> None:
    spec_client = _client(
        (None, [_tc("k1", "delete_event", event_id="e1")]),
        (None, [_tc("k2", "delete_event", event_id="e2")]),
    )
    _register_calendar(spec_client)
    comp_client = _client(
        (
            None,
            [_tc("d1", DELEGATE_TOOL_NAME, agent_name="calendar", objective="o")],
        ),
    )
    with pytest.raises(LoopParked) as info:
        await _Companion().agentic_loop(_comp_ctx(), comp_client, [], system="s")
    loop = info.value.loop
    first = loop.all_parked()[0].item_id
    ctx = _comp_ctx(
        resume=loop,
        write_decisions={first: WriteDecision(first, "approved")},
        write_round=1,
    )
    with pytest.raises(LoopParked) as again:
        await _Companion().agentic_loop(ctx, comp_client, [], system="s")
    new_loop = again.value.loop
    assert new_loop.child_call_id == "d1"
    assert [w.args for w in new_loop.all_parked()] == [{"event_id": "e2"}]
