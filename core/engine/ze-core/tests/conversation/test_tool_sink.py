from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from typing_extensions import TypedDict

from ze_agents.interface.types import RawInput
from ze_agents.types import ToolCall
from ze_core.orchestration.state import AgentState
from ze_core.conversation.turn import invoke_raw_turn, resume_turn
from ze_core.orchestration.timing import add_timed_node
from ze_core.routing.types import RoutingEnvelope, SubTask
from ze_core.telemetry import turn as turn_mod
from ze_core.telemetry.turn import TurnTelemetryRegistry


class State(TypedDict, total=False):
    prompt: str
    session_id: str
    envelope: Any
    memory_context: Any
    final_response: str | None
    message_trace: Any
    error: str | None


@dataclass
class _Fact:
    predicate: str
    value: str
    relevance_score: float
    confidence: float


@dataclass
class _Episode:
    summary: str
    relevance_score: float


@dataclass
class _Ctx:
    facts: list
    episodes: list


class Clock:
    now = 100.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch) -> Clock:
    fake = Clock()
    fake.now = 100.0
    monkeypatch.setattr(turn_mod, "monotonic", fake)
    return fake


def _frames(interface) -> list[dict]:
    return [call.args[1] for call in interface.send_trace_partial.await_args_list]


def _tool_rows(interface) -> list[dict]:
    return [r for f in _frames(interface) for r in f.get("tool_calls", [])]


def _container(graph):
    interface = MagicMock()
    interface.send_trace_partial = AsyncMock()
    c = SimpleNamespace(
        graph=graph,
        state_type=AgentState,
        interface=interface,
        turn_telemetry=TurnTelemetryRegistry(),
        _build_config=lambda thread_id, **kw: {
            "configurable": {"thread_id": thread_id, **kw}
        },
    )
    return c, interface


def _graph(nodes, order):
    builder = StateGraph(State)
    for name in order:
        add_timed_node(builder, name, nodes[name])
    builder.set_entry_point(order[0])
    for a, b in zip(order, order[1:]):
        builder.add_edge(a, b)
    builder.add_edge(order[-1], END)
    return builder.compile(checkpointer=MemorySaver())


async def test_the_sink_enqueues_a_live_row_with_offsets_from_the_monotonic_clock(
    clock,
):
    async def execute_tool(state, config):
        sink = config["configurable"]["tool_sink"]
        clock.now += 0.64
        call = ToolCall(
            tool_name="list_events",
            args={},
            result="3pm dentist",
            duration_ms=312,
            success=True,
            agent="calendar",
            started_at=clock.now,
        )
        sink(call)
        failed = ToolCall(
            tool_name="delete_event",
            args={},
            result="",
            duration_ms=45,
            success=False,
            error="nope",
            agent="calendar",
            started_at=clock.now + 0.4,
        )
        sink(failed)
        return {"final_response": "ok"}

    container, interface = _container(
        _graph({"execute_tool": execute_tool}, ["execute_tool"])
    )
    await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    rows = _tool_rows(interface)
    assert [r["name"] for r in rows] == ["list_events", "delete_event"]
    ok, bad = rows
    assert ok["start_offset_ms"] == 640
    assert (ok["duration_ms"], ok["success"], ok["agent"], ok["gate"]) == (
        312,
        True,
        "calendar",
        "none",
    )
    assert ok["result_snippet"] == "3pm dentist"
    assert ok["call_id"]
    assert bad["success"] is False and bad["duration_ms"] == 45
    assert bad["start_offset_ms"] == 1040
    assert set(ok) == {
        "call_id",
        "name",
        "agent",
        "gate",
        "start_offset_ms",
        "duration_ms",
        "success",
        "result_snippet",
    }


async def test_a_parked_row_reads_parked_and_keeps_its_call_id(clock):
    async def execute_tool(state, config):
        call = ToolCall(
            tool_name="delete_event",
            args={},
            result="",
            duration_ms=0,
            success=True,
            gate="parked",
            call_id="park-1",
        )
        config["configurable"]["tool_sink"](call)
        return {}

    container, interface = _container(
        _graph({"execute_tool": execute_tool}, ["execute_tool"])
    )
    await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    (row,) = _tool_rows(interface)
    assert (row["call_id"], row["gate"], row["start_offset_ms"]) == (
        "park-1",
        "parked",
        None,
    )


async def test_offset_is_null_when_the_call_is_out_of_range_or_the_recorder_partial(
    clock,
):
    async def execute_tool(state, config):
        sink = config["configurable"]["tool_sink"]
        sink(
            ToolCall(
                tool_name="before",
                args={},
                result="",
                duration_ms=1,
                success=True,
                started_at=clock.now - 50,
            )
        )
        return {}

    container, interface = _container(
        _graph({"execute_tool": execute_tool}, ["execute_tool"])
    )
    await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    assert _tool_rows(interface)[0]["start_offset_ms"] is None


async def test_the_sink_never_raises_into_the_tool(clock):
    seen = []

    async def execute_tool(state, config):
        sink = config["configurable"]["tool_sink"]
        sink(object())  # not a ToolCall
        seen.append("survived")
        return {}

    container, _ = _container(_graph({"execute_tool": execute_tool}, ["execute_tool"]))
    await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    assert seen == ["survived"]


async def test_resume_turn_builds_its_own_sink(clock):
    import langgraph.types as lg_types
    from ze_agents.park import ConfirmItem, WriteConfirmation

    async def ask(state, config):
        lg_types.interrupt(
            WriteConfirmation(
                request_id="r1",
                kind="write",
                round=1,
                items=[ConfirmItem("i", "a", "t", "e", "s")],
            )
        )
        config["configurable"]["tool_sink"](
            ToolCall(
                tool_name="after_resume",
                args={},
                result="x",
                duration_ms=2,
                success=True,
            )
        )
        return {}

    container, interface = _container(_graph({"ask": ask}, ["ask"]))
    first = await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    assert first.interrupted
    await resume_turn(
        container, first.config, resume={"choice": "approve"}, request_id="r1"
    )
    assert [r["name"] for r in _tool_rows(interface)] == ["after_resume"]


async def test_embed_route_partial_carries_top_nine_scores_and_thresholds(clock):
    scores = {f"agent{i}": 0.5 + i / 100 for i in range(12)}
    envelope = RoutingEnvelope(
        primary_agent="agent11",
        confidence=0.61,
        score_gap=0.01,
        routing_method="embedding",
        is_compound=False,
        subtasks=[SubTask("agent11", "p")],
        requires_synthesis=False,
        raw_scores=scores,
        threshold=0.78,
        gap_threshold=0.05,
    )

    async def embed_route(state, config):
        return {"envelope": envelope}

    container, interface = _container(
        _graph({"embed_route": embed_route}, ["embed_route"])
    )
    await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    (frame,) = [f for f in _frames(interface) if "routing_scores" in f]
    assert [s["agent"] for s in frame["routing_scores"]] == [
        f"agent{i}" for i in range(11, 2, -1)
    ]
    assert frame["routing_scores"][0] == {
        "agent": "agent11",
        "score": pytest.approx(0.61),
    }
    assert frame["routing_thresholds"] == {"threshold": 0.78, "gap": 0.05}
    assert frame["agent"] == "agent11"


async def test_a_forced_envelope_has_no_scores(clock):
    envelope = RoutingEnvelope(
        primary_agent="a",
        confidence=1.0,
        score_gap=1.0,
        routing_method="forced",
        is_compound=False,
        subtasks=[SubTask("a", "p")],
        requires_synthesis=False,
        raw_scores={"a": 1.0},
    )

    async def embed_route(state, config):
        return {"envelope": envelope}

    container, interface = _container(
        _graph({"embed_route": embed_route}, ["embed_route"])
    )
    await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    (frame,) = [f for f in _frames(interface) if "agent" in f]
    assert frame["routing_scores"] == []


async def test_memory_partial_carries_extraction_confidence_for_facts(clock):
    fact = _Fact("likes", "tea", 0.8, 0.9)
    memory_ctx = _Ctx([fact], [_Episode("talked", 0.4)])

    async def fetch_context(state, config):
        return {"memory_context": memory_ctx}

    container, interface = _container(
        _graph({"fetch_context": fetch_context}, ["fetch_context"])
    )
    await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    (frame,) = [f for f in _frames(interface) if "memory_chunks" in f]
    fact_chunk, episode_chunk = frame["memory_chunks"]
    assert fact_chunk["extraction_confidence"] == 0.9
    assert episode_chunk["extraction_confidence"] is None


async def test_the_on_tool_end_branch_is_gone(clock):
    interface = MagicMock()
    interface.send_trace_partial = AsyncMock()

    async def events(*a, **kw):
        yield {
            "event": "on_tool_end",
            "name": "list_events",
            "data": {"output": "x"},
        }
        yield {"event": "on_chain_end", "name": "LangGraph", "data": {"output": {}}}

    graph = MagicMock()
    graph.name = "LangGraph"
    graph.astream_events = events
    graph.aget_state = AsyncMock(return_value=MagicMock(next=()))
    container = SimpleNamespace(
        graph=graph,
        state_type=AgentState,
        interface=interface,
        turn_telemetry=TurnTelemetryRegistry(),
        _build_config=lambda thread_id, **kw: {
            "configurable": {"thread_id": thread_id}
        },
    )
    await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    interface.send_trace_partial.assert_not_awaited()
