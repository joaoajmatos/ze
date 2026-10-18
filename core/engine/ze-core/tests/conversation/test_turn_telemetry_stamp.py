from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Annotated, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END
from langgraph.graph import StateGraph
import langgraph.types as lg_types
from typing_extensions import TypedDict

from ze_agents.interface.types import RawInput
from ze_agents.park import ConfirmItem, WriteConfirmation
from ze_core.conversation.messages.types import MessageTrace
from ze_core.conversation.turn import invoke_raw_turn, resume_turn
from ze_core.orchestration.timing import add_timed_node
from ze_core.telemetry import turn as turn_mod
from ze_core.telemetry.turn import TurnTelemetryRegistry


class State(TypedDict, total=False):
    prompt: str
    session_id: str
    final_response: str | None
    message_trace: Any
    error: str | None
    seen: Annotated[list, lambda a, b: (a or []) + (b or [])]


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch) -> Clock:
    fake = Clock()
    monkeypatch.setattr(turn_mod, "monotonic", fake)
    return fake


def _trace() -> MessageTrace:
    return MessageTrace(
        agent="a",
        routing_method="embedding",
        confidence=1.0,
        score_gap=0.0,
        is_compound=False,
        subtasks=[],
    )


def _confirmation() -> WriteConfirmation:
    return WriteConfirmation(
        request_id="r1",
        kind="write",
        round=1,
        items=[
            ConfirmItem(
                item_id="i1",
                agent="calendar",
                tool="delete_event",
                effect_phrase="deleted an event",
                summary="3pm",
            )
        ],
    )


def _graph(clock: Clock, *, pause: bool = False, fail_after_trace: bool = False):
    async def a(state, config):
        clock.now += 0.1
        return {"seen": ["a"]}

    async def ask(state, config):
        if pause:
            lg_types.interrupt(_confirmation())
        clock.now += 0.2
        return {"seen": ["ask"]}

    async def record_trace(state, config):
        clock.now += 0.05
        return {"message_trace": _trace(), "final_response": "Done."}

    async def write_memory(state, config):
        if fail_after_trace:
            return {"error": "memory exploded"}
        return {}

    builder = StateGraph(State)
    for name, fn in (
        ("a", a),
        ("ask", ask),
        ("record_trace", record_trace),
        ("write_memory", write_memory),
    ):
        add_timed_node(builder, name, fn)
    builder.set_entry_point("a")
    builder.add_edge("a", "ask")
    builder.add_edge("ask", "record_trace")
    builder.add_edge("record_trace", "write_memory")
    builder.add_edge("write_memory", END)
    return builder.compile(checkpointer=MemorySaver())


def _container(graph, interface=None):
    c = SimpleNamespace()
    c.graph = graph
    c.interface = interface
    c.turn_telemetry = TurnTelemetryRegistry()
    c._build_config = lambda thread_id, **kw: {
        "configurable": {"thread_id": thread_id, **kw}
    }
    return c


def _interface():
    interface = MagicMock()
    interface.send_trace_partial = AsyncMock()
    return interface


async def test_invoke_raw_turn_stamps_stages_and_totals(clock):
    container = _container(_graph(clock), _interface())
    outcome = await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    trace = outcome.final_state["message_trace"]
    assert [(s.name, s.run) for s in trace.stages] == [
        ("a", 1),
        ("ask", 1),
        ("record_trace", 1),
        ("write_memory", 1),
    ]
    assert trace.turn_duration_ms >= sum(s.duration_ms for s in trace.stages)
    assert trace.paused_ms == 0
    assert trace.telemetry_partial is False
    assert container.turn_telemetry.resume("t1").partial is True  # entry was finished


async def test_stage_frames_precede_the_committed_trace(clock):
    interface = _interface()
    order: list[str] = []

    async def slow_first(message_id, fields, thread_id=None):
        if "stages" in fields and not order:
            await asyncio.sleep(0.1)
        order.append(fields["stages"][0]["name"] if "stages" in fields else "x")

    interface.send_trace_partial = slow_first
    container = _container(_graph(clock), interface)
    await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    # invoke_raw_turn drained before returning: every stage frame was already sent.
    assert order == ["a", "ask", "record_trace", "write_memory"]


async def test_interrupted_run_keeps_recorder_and_resume_continues_it(clock):
    graph = _graph(clock, pause=True)
    container = _container(graph, _interface())
    first = await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    assert first.interrupted
    assert first.final_state.get("message_trace") is None
    clock.now += 20  # the user takes their time

    # Second run: the node no longer pauses once resumed with a decision.
    resumed = await resume_turn(
        container, first.config, resume={"choice": "approve"}, request_id="r1"
    )
    assert not resumed.interrupted
    trace = resumed.final_state["message_trace"]
    runs = [(s.name, s.run) for s in trace.stages]
    assert runs[0] == ("a", 1)
    assert ("ask", 1) in runs and ("ask", 2) in runs
    assert trace.paused_ms == 20000
    assert trace.turn_duration_ms >= 20000
    assert trace.telemetry_partial is False


async def test_resume_after_restart_is_partial(clock):
    graph = _graph(clock, pause=True)
    container = _container(graph, _interface())
    first = await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    container.turn_telemetry = TurnTelemetryRegistry()  # the process restarted
    resumed = await resume_turn(
        container, first.config, resume={"choice": "approve"}, request_id="r1"
    )
    trace = resumed.final_state["message_trace"]
    assert trace.telemetry_partial is True
    assert {s.run for s in trace.stages} == {1}  # the new recorder starts at run 1


async def test_a_turn_that_errors_after_record_trace_keeps_the_stages(clock):
    container = _container(_graph(clock, fail_after_trace=True), _interface())
    outcome = await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    assert outcome.error == "memory exploded"
    names = [s.name for s in outcome.final_state["message_trace"].stages]
    assert names == ["a", "ask", "record_trace", "write_memory"]


async def test_a_raising_graph_leaves_no_entry_behind(clock):
    graph = MagicMock()
    graph.name = "LangGraph"

    async def boom(*a, **kw):
        raise RuntimeError("graph died")
        yield  # pragma: no cover

    graph.astream_events = boom
    container = _container(graph)
    with pytest.raises(RuntimeError):
        await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    assert container.turn_telemetry.resume("t1").partial is True


async def test_a_new_turn_on_a_paused_thread_replaces_the_recorder(clock):
    graph = _graph(clock, pause=True)
    container = _container(graph, _interface())
    await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    paused = container.turn_telemetry.resume("t1")
    paused.pause()
    await invoke_raw_turn(container, "t1", RawInput(text="again"))
    assert container.turn_telemetry.resume("t1") is not paused


async def test_retry_turn_starts_a_fresh_recorder(clock):
    container = _container(_graph(clock), _interface())
    first = await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    second = await invoke_raw_turn(
        container, "t1", RawInput(text="hi"), config_extra={"retry_mode": True}
    )
    one = first.final_state["message_trace"]
    two = second.final_state["message_trace"]
    assert [s.name for s in two.stages] == ["a", "ask", "record_trace", "write_memory"]
    assert [s.name for s in one.stages] == [s.name for s in two.stages]
    assert two.stages[0].start_ms == 0


async def test_a_container_without_a_registry_runs_untimed(clock):
    container = _container(_graph(clock))
    container.turn_telemetry = None
    outcome = await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    assert outcome.final_state["message_trace"].stages == []


async def test_work_after_the_stamp_adds_nothing(clock):
    container = _container(_graph(clock))
    outcome = await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    trace = outcome.final_state["message_trace"]
    stages_before = list(trace.stages)
    late = TurnTelemetryRegistry().start("zz")
    late.stamp(_trace())
    late.record_stage("late", clock.now, clock.now + 1)
    assert late.stages == []
    assert trace.stages == stages_before


async def test_resume_with_nothing_pending_finishes_the_entry(clock):
    container = _container(_graph(clock, pause=True), _interface())
    first = await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    await resume_turn(container, first.config, resume={"choice": "approve"})
    # The timeout path calls resume_turn once more; the graph holds nothing now.
    outcome = await resume_turn(
        container, first.config, resume={"choice": "timeout"}, request_id="r1"
    )
    assert outcome.error == "No pending confirmation."
    assert container.turn_telemetry._entries == {}


async def test_a_stale_answer_does_not_end_the_live_recorder(clock):
    container = _container(_graph(clock, pause=True), _interface())
    first = await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    outcome = await resume_turn(
        container, first.config, resume={"choice": "approve"}, request_id="old"
    )
    assert outcome.error == "No pending confirmation."
    assert "t1" in container.turn_telemetry._entries


def test_main_model_prefers_tier_then_agent_then_synthesis():
    from ze_agents.types import AgentContext
    from ze_core.conversation.messages.types import TierTrace
    from ze_core.conversation.turn import _main_model

    ctx = AgentContext(session_id="s", prompt="p", model="agent/model")
    tier = TierTrace("calendar", "simple", "judge", "tier/model")
    assert _main_model({"agent_context": ctx, "tier": tier}, {}) == "tier/model"
    assert _main_model({"agent_context": ctx}, {}) == "agent/model"
    assert _main_model({}, {}) is None
    compound = SimpleNamespace(is_compound=True)
    from ze_agents.defaults import MODEL_SYNTHESIS

    assert (
        _main_model({"envelope": compound, "agent_context": ctx, "tier": tier}, {})
        == MODEL_SYNTHESIS
    )
    override = SimpleNamespace(config={"models": {"overrides": {"synthesis": "x/y"}}})
    assert (
        _main_model({"envelope": compound}, {"configurable": {"settings": override}})
        == "x/y"
    )
