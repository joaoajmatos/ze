"""Every return path of `BaseAgent.call_tool` hands one ToolCall to `ctx.tool_sink` (187b)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.errors import LoopParked, UnknownToolError
from ze_agents.hooks import BaseHarnessHook, clear_hooks, register_hook
from ze_agents.errors import HookAbort
from ze_agents.park import ApprovedCall, WriteDecision
from ze_agents.registry import clear_registry
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext, AgentResult, ToolCall, WriteGateState


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()

    async def read_it() -> str:
        return "ok"

    tool(access=ToolAccess.READ, description="read")(read_it)

    async def boom() -> str:
        raise RuntimeError("bad")

    tool(access=ToolAccess.READ, description="boom")(boom)

    async def delete_event(event_id: str = "") -> str:
        return "deleted"

    tool(
        access=ToolAccess.WRITE,
        description="delete",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="deleted a calendar event",
    )(delete_event)
    yield
    clear_registry()
    clear_tool_registry()


class _Agent(BaseAgent):
    name = "calendar"
    description = "test"
    tools = ["read_it", "boom", "delete_event"]

    async def run(self, ctx: AgentContext) -> AgentResult:  # pragma: no cover
        raise NotImplementedError


_GATE_KW = {
    "resume": "resume",
    "write_decisions": "decisions",
    "pre_approved_writes": "pre_approved",
    "write_round": "round",
    "approval_request_id": "approval_request_id",
    "loop_active": "loop_active",
    "retry_mode": "retry_mode",
}


def _gate(kw: dict, **defaults) -> dict:
    """Fold the write-gate keyword names a test passes into one `WriteGateState`."""
    gate = {_GATE_KW[k]: kw.pop(k) for k in list(kw) if k in _GATE_KW}
    return {"write_gate": WriteGateState(**{**defaults, **gate}), **kw}


def _ctx(sink, **kw) -> AgentContext:
    return AgentContext(
        session_id="s", prompt="p", tool_sink=sink, **_gate(kw, loop_active=True)
    )


async def test_success_reaches_the_sink_once_with_started_at() -> None:
    seen: list[ToolCall] = []
    tc = await _Agent().call_tool("read_it", _ctx(seen.append))
    assert seen == [tc]
    assert tc.started_at is not None and tc.success


async def test_exception_reaches_the_sink_with_its_duration() -> None:
    seen: list[ToolCall] = []
    tc = await _Agent().call_tool("boom", _ctx(seen.append))
    assert seen == [tc]
    assert tc.success is False and tc.started_at is not None


async def test_unknown_tool_reaches_the_sink_and_still_raises() -> None:
    seen: list[ToolCall] = []
    with pytest.raises(UnknownToolError):
        await _Agent().call_tool("nope", _ctx(seen.append))
    assert len(seen) == 1
    assert seen[0].tool_name == "nope" and seen[0].success is False
    assert seen[0].started_at is None


async def test_refused_retry_write_reaches_the_sink() -> None:
    seen: list[ToolCall] = []
    tc = await _Agent().call_tool(
        "delete_event", _ctx(seen.append, retry_mode=True), event_id="e1"
    )
    assert tc.gate == "refused" and seen == [tc]
    assert tc.started_at is None


async def test_parked_call_uses_the_trace_call_id() -> None:
    seen: list[ToolCall] = []
    tc = await _Agent().call_tool(
        "delete_event",
        _ctx(seen.append),
        _lm_args={"event_id": "e1"},
        _call_id="call_0",
        event_id="e1",
    )
    assert seen == [tc] and tc.gate == "parked"
    assert tc.call_id == tc.parked.trace_call_id
    assert tc.parked.call_id == "call_0"


async def test_approved_run_keeps_the_parked_call_id() -> None:
    seen: list[ToolCall] = []
    parked = await _Agent().call_tool(
        "delete_event", _ctx(seen.append), _call_id="call_0", event_id="e1"
    )
    approved = await _Agent().call_tool(
        "delete_event",
        _ctx(seen.append),
        _approval=ApprovedCall("call_0"),
        _trace_call_id=parked.parked.trace_call_id,
        event_id="e1",
    )
    assert approved.gate == "approved" and approved.started_at is not None
    assert approved.call_id == parked.call_id
    assert [c.call_id for c in seen] == [parked.call_id, parked.call_id]


async def test_pre_approved_reaches_the_sink() -> None:
    seen: list[ToolCall] = []
    ctx = _ctx(seen.append, pre_approved_writes=frozenset({"delete_event"}))
    tc = await _Agent().call_tool("delete_event", ctx, event_id="e1")
    assert tc.gate == "pre_approved" and seen == [tc]


async def test_hook_skip_reaches_the_sink() -> None:
    class _Skip(BaseHarnessHook):
        async def on_tool_start(self, event):
            raise HookAbort("no", result="skipped")

    clear_hooks()
    register_hook(_Skip())
    try:
        seen: list[ToolCall] = []
        tc = await _Agent().call_tool("read_it", _ctx(seen.append))
        assert seen == [tc] and tc.success is False
    finally:
        clear_hooks()


async def test_a_raising_sink_does_not_change_the_result() -> None:
    def bad(call: ToolCall) -> None:
        raise RuntimeError("sink down")

    tc = await _Agent().call_tool("read_it", _ctx(bad))
    assert tc.success and tc.result == "ok"


async def test_no_sink_is_fine() -> None:
    tc = await _Agent().call_tool("read_it", _ctx(None))
    assert tc.success


def _client(*responses):
    client = MagicMock()
    client.complete_with_tools = AsyncMock(side_effect=list(responses))
    client.complete = AsyncMock(return_value="fallback")
    return client


async def test_denied_resume_reaches_the_sink_with_the_parked_id() -> None:
    seen: list[ToolCall] = []
    client = _client((None, [{"id": "c1", "name": "delete_event", "arguments": {}}]))
    with pytest.raises(LoopParked) as info:
        await _Agent().agentic_loop(_ctx(seen.append), client, [], system="s")
    loop = info.value.loop
    parked_id = loop.parked[0].trace_call_id
    seen.clear()
    ctx = _ctx(
        seen.append,
        resume=loop,
        write_decisions={
            loop.parked[0].item_id: WriteDecision(loop.parked[0].item_id, "denied")
        },
        write_round=1,
    )
    await _Agent().agentic_loop(ctx, _client(("ok", None)), [], system="s")
    assert [(c.gate, c.call_id) for c in seen] == [("denied", parked_id)]


async def test_approved_resume_shares_the_id_of_the_parked_row() -> None:
    seen: list[ToolCall] = []
    client = _client((None, [{"id": "c1", "name": "delete_event", "arguments": {}}]))
    with pytest.raises(LoopParked) as info:
        await _Agent().agentic_loop(_ctx(seen.append), client, [], system="s")
    loop = info.value.loop
    parked_row = seen[0]
    seen.clear()
    ctx = _ctx(
        seen.append,
        resume=loop,
        write_decisions={
            loop.parked[0].item_id: WriteDecision(loop.parked[0].item_id, "approved")
        },
        write_round=1,
    )
    await _Agent().agentic_loop(ctx, _client(("ok", None)), [], system="s")
    assert [c.gate for c in seen] == ["approved"]
    assert seen[0].call_id == parked_row.call_id


async def test_colliding_provider_ids_get_distinct_call_ids() -> None:
    seen: list[ToolCall] = []
    a = await _Agent().call_tool("delete_event", _ctx(seen.append), _call_id="call_0")
    b = await _Agent().call_tool("delete_event", _ctx(seen.append), _call_id="call_0")
    assert a.call_id != b.call_id
