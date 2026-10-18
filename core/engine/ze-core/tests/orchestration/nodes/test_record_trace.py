"""record_trace: committed tool rows, durations and routing fields (187b)."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from ze_agents.delegate import DELEGATE_TOOL_NAME
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext, AgentResult, ToolCall
from ze_core.orchestration.nodes.trace import record_trace
from ze_core.telemetry.turn import current_turn_telemetry


@pytest.fixture(autouse=True)
def tools():
    clear_tool_registry()

    @tool(access=ToolAccess.READ, description="r")
    async def lookup() -> str: ...

    yield
    clear_tool_registry()


@pytest.fixture
def recorder():
    """A recorder that started 10 s ago; `partial` is toggled per test."""
    rec = SimpleNamespace(started=time.monotonic() - 10.0, partial=False)
    token = current_turn_telemetry.set(rec)
    yield rec
    current_turn_telemetry.reset(token)


def _envelope(**kw) -> SimpleNamespace:
    base = dict(
        primary_agent="companion",
        routing_method="embedding",
        confidence=0.8,
        score_gap=0.2,
        is_compound=False,
        subtasks=[],
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _state(result=None, subtasks=None, envelope=None) -> dict:
    return {
        "envelope": envelope or _envelope(),
        "agent_result": result,
        "subtask_results": subtasks or [],
        "agent_context": AgentContext(session_id="s", prompt="x"),
    }


def _call(name="lookup", *, duration_ms=1, started_at=None, **kw) -> ToolCall:
    return ToolCall(
        tool_name=name,
        args={},
        result="ok",
        duration_ms=duration_ms,
        success=True,
        started_at=started_at,
        **kw,
    )


async def _trace(state: dict):
    return (await record_trace(state, {"configurable": {}}))["message_trace"]


async def test_tool_duration_is_the_sum_of_tool_durations() -> None:
    result = AgentResult(
        agent="companion",
        response="ok",
        tool_calls=[_call(duration_ms=120), _call(duration_ms=80)],
    )
    trace = await _trace(_state(result))
    assert trace.tool_duration_ms == 200


async def test_rows_carry_call_id_and_offset_from_the_recorder(recorder) -> None:
    call = _call(started_at=recorder.started + 0.640)
    trace = await _trace(
        _state(AgentResult(agent="c", response="ok", tool_calls=[call]))
    )
    assert trace.tool_calls[0].call_id == call.call_id
    assert trace.tool_calls[0].start_offset_ms == 640


async def test_offset_is_null_without_a_recorder() -> None:
    call = _call(started_at=time.monotonic())
    trace = await _trace(
        _state(AgentResult(agent="c", response="ok", tool_calls=[call]))
    )
    assert trace.tool_calls[0].call_id == call.call_id
    assert trace.tool_calls[0].start_offset_ms is None


async def test_offset_is_null_for_a_partial_recorder(recorder) -> None:
    recorder.partial = True
    call = _call(started_at=recorder.started + 1.0)
    trace = await _trace(
        _state(AgentResult(agent="c", response="ok", tool_calls=[call]))
    )
    assert trace.tool_calls[0].start_offset_ms is None


async def test_offset_is_null_when_out_of_range(recorder) -> None:
    before = _call(started_at=recorder.started - 5.0)
    after = _call(started_at=time.monotonic() + 500.0)
    unrun = _call(started_at=None)
    result = AgentResult(agent="c", response="ok", tool_calls=[before, after, unrun])
    trace = await _trace(_state(result))
    assert [t.start_offset_ms for t in trace.tool_calls] == [None, None, None]


async def test_compound_rows_keep_the_live_call_ids_and_flattened_index(
    recorder,
) -> None:
    a = _call(started_at=recorder.started + 1.0)
    b = _call(started_at=recorder.started + 2.0)
    c = _call(started_at=recorder.started + 3.0)
    subs = [
        AgentResult(agent="alpha", response="1", tool_calls=[a, b]),
        AgentResult(agent="beta", response="2", tool_calls=[c]),
    ]
    trace = await _trace(
        _state(None, subtasks=subs, envelope=_envelope(is_compound=True, subtasks=[]))
    )
    assert [t.call_id for t in trace.tool_calls] == [a.call_id, b.call_id, c.call_id]
    assert [t.call_index for t in trace.tool_calls] == [0, 1, 2]
    assert [t.start_offset_ms for t in trace.tool_calls] == [1000, 2000, 3000]


async def test_delegate_rows_keep_the_ids_their_live_rows_carried(recorder) -> None:
    from ze_agents.nested_tools import flatten_tool_calls  # noqa: F401

    live = _call(started_at=recorder.started + 4.0, agent="calendar")
    nested = {
        "tool_name": live.tool_name,
        "args": {},
        "result": "ok",
        "duration_ms": 1,
        "success": True,
        "gate": "none",
        "agent": "calendar",
        "call_id": live.call_id,
        "started_at": live.started_at,
    }
    delegate = ToolCall(
        tool_name=DELEGATE_TOOL_NAME,
        args={},
        result={"response": "done", "tool_calls": [nested]},
        duration_ms=5,
        success=True,
        agent="companion",
    )
    trace = await _trace(
        _state(AgentResult(agent="companion", response="ok", tool_calls=[delegate]))
    )
    assert [t.name for t in trace.tool_calls] == [DELEGATE_TOOL_NAME, "lookup"]
    inner = trace.tool_calls[1]
    assert inner.call_id == live.call_id
    assert inner.start_offset_ms == 4000
    assert inner.call_index == 1


async def test_routing_scores_are_the_top_nine_highest_first() -> None:
    scores = {f"a{i}": i / 20 for i in range(12)}
    trace = await _trace(
        _state(
            envelope=_envelope(raw_scores=scores, threshold=0.78, gap_threshold=0.05)
        )
    )
    assert [s.agent for s in trace.routing_scores] == [
        f"a{i}" for i in range(11, 2, -1)
    ]
    assert trace.routing_scores[0].score == pytest.approx(11 / 20)
    assert trace.routing_thresholds.threshold == 0.78
    assert trace.routing_thresholds.gap == 0.05


async def test_a_single_forced_score_gives_no_routing_scores() -> None:
    trace = await _trace(
        _state(
            envelope=_envelope(
                routing_method="forced",
                raw_scores={"companion": 1.0},
                threshold=0.78,
                gap_threshold=0.05,
            )
        )
    )
    assert trace.routing_scores == []
    assert trace.routing_thresholds is not None


async def test_an_envelope_without_scores_or_thresholds_is_empty() -> None:
    trace = await _trace(_state())
    assert trace.routing_scores == []
    assert trace.routing_thresholds is None
