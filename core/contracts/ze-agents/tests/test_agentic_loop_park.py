"""`agentic_loop` parks asks-first calls and raises LoopParked (Phase 181, D2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.errors import LoopParked
from ze_agents.registry import clear_registry
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, clear_tool_registry, tool, undo_payload
from ze_agents.types import AgentContext, AgentResult, WriteGateState

calls: list[tuple[str, dict]] = []


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    calls.clear()

    async def list_events() -> str:
        calls.append(("list_events", {}))
        return "3pm dentist"

    tool(access=ToolAccess.READ, description="list")(list_events)

    async def delete_event(event_id: str = "") -> str:
        calls.append(("delete_event", {"event_id": event_id}))
        return "deleted"

    tool(
        access=ToolAccess.WRITE,
        description="delete",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="deleted a calendar event",
    )(delete_event)

    async def send_email(to: str = "") -> str:
        calls.append(("send_email", {"to": to}))
        return "sent"

    tool(
        access=ToolAccess.WRITE,
        description="send",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="sent an email",
    )(send_email)

    async def remove_note(note_id: str = "") -> str:
        calls.append(("remove_note", {"note_id": note_id}))
        return "removed"

    tool(
        access=ToolAccess.WRITE,
        description="remove",
        reversibility=ToolReversibility.IRREVERSIBLE,
        asks_first=False,
        no_ask_reason="undo of an approved note",
    )(remove_note)

    async def add_note(text: str = "") -> dict:
        calls.append(("add_note", {"text": text}))
        return {"ok": True, "undo": undo_payload(note_id="n1")}

    tool(
        access=ToolAccess.WRITE,
        description="note",
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="remove_note",
        undo_note="removes the note",
    )(add_note)
    yield
    clear_registry()
    clear_tool_registry()


class _Agent(BaseAgent):
    name = "calendar"
    description = "test"
    tools = ["list_events", "delete_event", "send_email"]

    async def run(self, ctx: AgentContext) -> AgentResult:
        return AgentResult(agent=self.name, response="ok")


def _ctx() -> AgentContext:
    return AgentContext(
        session_id="s",
        prompt="p",
    )


def _client(*responses):
    client = MagicMock()
    client.complete_with_tools = AsyncMock(side_effect=list(responses))
    client.complete = AsyncMock(return_value="fallback")
    return client


def _tc(id_: str, name: str, **args):
    return {"id": id_, "name": name, "arguments": args}


async def test_read_runs_write_parks() -> None:
    ctx = _ctx()
    client = _client(
        (None, [_tc("c1", "list_events"), _tc("c2", "delete_event", event_id="e1")])
    )
    with pytest.raises(LoopParked) as info:
        await _Agent().agentic_loop(
            ctx, client, [{"role": "user", "content": "delete my 3pm"}], system="s"
        )
    loop = info.value.loop
    assert calls == [("list_events", {})]
    assert loop.agent == "calendar"
    assert loop.iteration == 0
    assert [a.tool_name for a in loop.accumulated] == ["list_events"]
    assert [(p.call_id, p.tool, p.args) for p in loop.parked] == [
        ("c2", "delete_event", {"event_id": "e1"})
    ]
    roles = [m["role"] for m in loop.messages]
    assert roles == ["user", "assistant", "tool"]
    assert loop.messages[-1]["tool_call_id"] == "c1"
    assert ctx.write_gate.loop_active is False


async def test_two_parked_calls_keep_model_order() -> None:
    client = _client(
        (
            None,
            [_tc("c1", "delete_event", event_id="a"), _tc("c2", "send_email", to="x")],
        )
    )
    with pytest.raises(LoopParked) as info:
        await _Agent().agentic_loop(_ctx(), client, [], system="s")
    assert [p.tool for p in info.value.loop.parked] == ["delete_event", "send_email"]
    assert calls == []


async def test_loop_active_inside_the_loop() -> None:
    ctx = _ctx()
    seen: list[bool] = []

    async def _complete(**kw):
        seen.append(ctx.write_gate.loop_active)
        return ("done", None)

    client = MagicMock()
    client.complete_with_tools = AsyncMock(side_effect=_complete)
    await _Agent().agentic_loop(ctx, client, [], system="s")
    assert seen == [True]
    assert ctx.write_gate.loop_active is False


async def test_iteration_recorded_after_earlier_iterations() -> None:
    client = _client(
        (None, [_tc("c1", "list_events")]),
        (None, [_tc("c2", "delete_event", event_id="e1")]),
    )
    with pytest.raises(LoopParked) as info:
        await _Agent().agentic_loop(_ctx(), client, [], system="s")
    assert info.value.loop.iteration == 1
    assert [a.tool_name for a in info.value.loop.accumulated] == ["list_events"]


# ── tool scripts: proposed writes (197) ───────────────────────────────────────


class _ScriptAgent(_Agent):
    tools = ["list_events", "delete_event", "send_email", "add_note"]


class _Runner:
    def __init__(self, writes):
        self.writes = writes

    async def run(
        self,
        *,
        script_id,
        agent,
        source,
        stub,
        limits,
        dispatch,
        procedure_id=None,
        context=None,
    ):
        from ze_agents.scripts import ScriptOutcome

        return ScriptOutcome(status="ok", value={"done": True}, writes=self.writes)


def _script_ctx(writes, **kw) -> AgentContext:
    names = {"write_decisions": "decisions", "write_round": "round"}
    gate = {
        names.get(k, k): kw.pop(k)
        for k in list(kw)
        if k in ("resume", "retry_mode", "write_decisions", "write_round")
    }
    ctx = AgentContext(session_id="s", prompt="p", write_gate=WriteGateState(**gate), **kw)
    ctx.script_runner = _Runner(writes)
    return ctx


def _script_call(id_: str = "c1"):
    return _tc(id_, "run_tool_script", source="x")


_DELETE = {"tool": "delete_event", "args": {"event_id": "e1"}}
_NOTE = {"tool": "add_note", "args": {"text": "hello"}}


async def test_script_writes_park_and_run_like_direct_calls() -> None:
    client = _client((None, [_script_call()]))
    messages: list[dict] = []
    with pytest.raises(LoopParked) as info:
        await _ScriptAgent().agentic_loop(
            _script_ctx([_DELETE, _NOTE]), client, messages, system="s"
        )
    loop = info.value.loop
    assert [(p.call_id, p.tool) for p in loop.parked] == [("c1_w0", "delete_event")]
    assert calls == [("add_note", {"text": "hello"})]
    step, note = loop.accumulated
    assert step.tool_name == "run_tool_script"
    assert note.tool_name == "add_note"
    assert note.undo == {"note_id": "n1"}
    assert note.parent_call_id == step.call_id
    saved = [tc["id"] for tc in loop.messages[0]["tool_calls"]]
    assert saved == ["c1", "c1_w0", "c1_w1"]
    answered = [m["tool_call_id"] for m in loop.messages if m["role"] == "tool"]
    assert answered == ["c1", "c1_w1"]


async def test_synthetic_ids_are_sanitized_and_cut() -> None:
    import re

    model_id = "toolu:" + "a" * 70
    client = _client((None, [_script_call(model_id)]))
    with pytest.raises(LoopParked) as info:
        await _ScriptAgent().agentic_loop(
            _script_ctx([_DELETE]), client, [], system="s"
        )
    parked_id = info.value.loop.parked[0].call_id
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", parked_id)
    assert parked_id.endswith("_w0") and len(parked_id) == 64


async def test_approved_proposal_runs_after_resume_with_its_parent() -> None:
    from ze_agents.park import WriteDecision

    client = _client((None, [_script_call()]))
    with pytest.raises(LoopParked) as info:
        await _ScriptAgent().agentic_loop(
            _script_ctx([_DELETE]), client, [], system="s"
        )
    loop = info.value.loop
    calls.clear()
    ctx = _script_ctx(
        [],
        resume=loop,
        write_decisions={
            loop.parked[0].item_id: WriteDecision(loop.parked[0].item_id, "approved")
        },
        write_round=1,
    )
    _, accumulated = await _ScriptAgent().agentic_loop(
        ctx, _client(("Done.", None)), [], system="s"
    )
    assert calls == [("delete_event", {"event_id": "e1"})]
    step = accumulated[0]
    deleted = accumulated[-1]
    assert deleted.tool_name == "delete_event" and deleted.gate == "approved"
    assert deleted.parent_call_id == step.call_id


async def test_retry_mode_refuses_the_irreversible_proposal() -> None:
    client = _client((None, [_script_call()]), ("Said it.", None))
    _, accumulated = await _ScriptAgent().agentic_loop(
        _script_ctx([_DELETE, _NOTE], retry_mode=True), client, [], system="s"
    )
    refused = [c for c in accumulated if c.tool_name == "delete_event"][0]
    assert refused.gate == "refused" and refused.success is False
    assert ("delete_event", {"event_id": "e1"}) not in calls
    assert ("add_note", {"text": "hello"}) in calls


async def test_proposals_are_refused_over_the_round_cap() -> None:
    from ze_agents.park import MAX_WRITE_ROUNDS

    client = _client((None, [_script_call()]), ("Okay.", None))
    _, accumulated = await _ScriptAgent().agentic_loop(
        _script_ctx([_DELETE], write_round=MAX_WRITE_ROUNDS), client, [], system="s"
    )
    refused = [c for c in accumulated if c.tool_name == "delete_event"][0]
    assert refused.gate == "refused_over_cap"
    assert calls == []


async def test_bad_proposals_become_not_a_proposable_write() -> None:
    writes = [
        {"tool": "list_events", "args": {}},
        {"tool": "no_such_tool", "args": {}},
        {"tool": "add_note"},
        "garbage",
    ] + [{"tool": "add_note", "args": {"text": str(i)}} for i in range(9)]
    client = _client((None, [_script_call()]), ("Done.", None))
    _, accumulated = await _ScriptAgent().agentic_loop(
        _script_ctx(writes), client, [], system="s"
    )
    rejected = [c for c in accumulated if c.error == "not_a_proposable_write"]
    assert len(rejected) == 4 + 3
    assert all(c.parent_call_id == accumulated[0].call_id for c in rejected)
    assert len([c for c in calls if c[0] == "add_note"]) == 6
    sent = client.complete_with_tools.call_args.kwargs["messages"]
    answered = {m["tool_call_id"] for m in sent if m["role"] == "tool"}
    declared = {tc["id"] for m in sent if m.get("tool_calls") for tc in m["tool_calls"]}
    assert declared == answered


@pytest.mark.parametrize("outcome", ["denied", "duplicate"])
async def test_denied_and_duplicate_proposals_keep_their_script_parent(outcome) -> None:
    from ze_agents.park import WriteDecision

    client = _client((None, [_script_call()]))
    with pytest.raises(LoopParked) as info:
        await _ScriptAgent().agentic_loop(
            _script_ctx([_DELETE]), client, [], system="s"
        )
    loop = info.value.loop
    item = loop.parked[0].item_id
    ctx = _script_ctx(
        [],
        resume=loop,
        write_decisions={item: WriteDecision(item, outcome)},
        write_round=1,
    )
    _, accumulated = await _ScriptAgent().agentic_loop(
        ctx, _client(("Done.", None)), [], system="s"
    )
    row = [c for c in accumulated if c.tool_name == "delete_event"][0]
    assert row.gate == outcome
    assert row.parent_call_id == accumulated[0].call_id
