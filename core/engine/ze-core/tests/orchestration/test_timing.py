from __future__ import annotations

import functools
from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.types import Command, interrupt

from ze_agents.registry import clear_registry
from ze_agents.tool import clear_tool_registry
from ze_core.orchestration.graph import graph_builder
from ze_core.orchestration.timing import add_timed_node, timed
from ze_core.telemetry.turn import TurnTelemetryRegistry, current_turn_telemetry

from tests.orchestration import write_confirmation_harness as h


class S(TypedDict, total=False):
    log: list


@pytest.fixture
def recorder():
    registry = TurnTelemetryRegistry()
    telemetry = registry.start("t")
    sent: list[dict] = []

    async def send(fields):
        sent.append(fields)

    telemetry.set_send(send)
    token = current_turn_telemetry.set(telemetry)
    yield telemetry, sent
    current_turn_telemetry.reset(token)


async def _a(state, config):
    return {"log": ["a"]}


async def _b(state, config):
    return {"log": ["b"]}


async def _c(state, config):
    return {"log": ["c"]}


def _three_node_graph():
    builder = StateGraph(S)
    for name, fn in (("a", _a), ("b", _b), ("c", _c)):
        add_timed_node(builder, name, fn)
    builder.set_entry_point("a")
    builder.add_edge("a", "b")
    builder.add_edge("b", "c")
    builder.add_edge("c", END)
    return builder.compile(checkpointer=MemorySaver())


async def test_each_node_sends_one_partial_stage_in_order(recorder):
    telemetry, sent = recorder
    graph = _three_node_graph()
    await graph.ainvoke({}, {"configurable": {"thread_id": "x"}})
    await telemetry.drain()
    assert [f["stages"][0]["name"] for f in sent] == ["a", "b", "c"]
    assert [s.name for s in telemetry.stages] == ["a", "b", "c"]
    assert all(set(f) == {"stages"} for f in sent)
    assert set(sent[0]["stages"][0]) == {"name", "start_ms", "duration_ms", "run"}


async def test_graph_interrupt_still_records_the_stage(recorder):
    telemetry, _ = recorder

    async def ask(state, config):
        answer = interrupt("need you")
        return {"log": [answer]}

    builder = StateGraph(S)
    add_timed_node(builder, "ask", ask)
    builder.set_entry_point("ask")
    builder.add_edge("ask", END)
    graph = builder.compile(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "x"}}
    await graph.ainvoke({}, cfg)
    assert [(s.name, s.run) for s in telemetry.stages] == [("ask", 1)]
    telemetry.pause()
    telemetry.begin_resumed_run()
    await graph.ainvoke(Command(resume="ok"), cfg)
    assert [(s.name, s.run) for s in telemetry.stages] == [("ask", 1), ("ask", 2)]


async def test_no_recorder_only_calls_the_node():
    assert current_turn_telemetry.get() is None
    seen = {}

    async def node(state, config):
        seen["config"] = config
        return {"log": ["x"]}

    wrapped = timed("n", node)
    assert await wrapped({}, {"configurable": {}}) == {"log": ["x"]}
    assert seen["config"] == {"configurable": {}}


async def test_sync_partial_and_stateonly_nodes_work(recorder):
    telemetry, _ = recorder
    seen: dict = {}

    def sync_node(state, config):
        seen["sync"] = config
        return {"log": ["s"]}

    def with_extra(extra, state, config):
        seen["partial"] = (extra, config)
        return {"log": [extra]}

    async def state_only(state):
        seen["state_only"] = True
        return {"log": ["o"]}

    builder = StateGraph(S)
    add_timed_node(builder, "sync", sync_node)
    add_timed_node(builder, "partial", functools.partial(with_extra, "p"))
    add_timed_node(builder, "only", state_only)
    builder.set_entry_point("sync")
    builder.add_edge("sync", "partial")
    builder.add_edge("partial", "only")
    builder.add_edge("only", END)
    graph = builder.compile()
    await graph.ainvoke({}, {"configurable": {"thread_id": "x", "k": 1}})
    assert seen["sync"]["configurable"]["k"] == 1
    assert seen["partial"][1]["configurable"]["k"] == 1
    assert seen["state_only"]
    assert [s.name for s in telemetry.stages] == ["sync", "partial", "only"]


async def test_emit_failure_does_not_break_the_node(recorder):
    telemetry, _ = recorder

    def boom(fields):
        raise RuntimeError("emit failed")

    telemetry.emit = boom  # type: ignore[method-assign]
    graph = _three_node_graph()
    out = await graph.ainvoke({}, {"configurable": {"thread_id": "x"}})
    assert out["log"] == ["c"] or "c" in out["log"]


@pytest.fixture
def clean():
    clear_registry()
    clear_tool_registry()
    yield
    clear_registry()
    clear_tool_registry()


async def test_graph_builder_wraps_every_node(clean, recorder):
    telemetry, _ = recorder
    seen = []

    async def noop(state, config=None):
        return {}

    async def pre_route(state, config):
        seen.append("pre")
        return {}

    overrides = {
        name: noop
        for name in (
            "preprocess",
            "resolve_screen",
            "embed_route",
            "decompose",
            "fetch_context",
            "match_skills",
            "choose_tier",
            "preflight",
            "await_budget_confirmation",
            "execute_tool",
            "await_write_confirmation",
            "correlate",
            "surface_loops",
            "synthesize",
            "record_trace",
            "write_memory",
        )
    }
    builder = graph_builder(node_overrides=overrides, pre_route_node=pre_route)
    for name, node in builder.nodes.items():
        assert node.runnable is not None
    # Run the first segment: preprocess -> inject_routing_context -> resolve_screen -> embed_route.
    builder.add_conditional_edges(
        "embed_route",
        lambda s: "fetch_context",
        {"decompose": "decompose", "fetch_context": "fetch_context"},
    )
    builder.add_edge("decompose", "fetch_context")
    graph = builder.compile(checkpointer=MemorySaver())
    await graph.ainvoke(h.graph_input("hi"), {"configurable": {"thread_id": "wrap"}})
    names = [s.name for s in telemetry.stages]
    assert names[:4] == [
        "preprocess",
        "inject_routing_context",
        "resolve_screen",
        "embed_route",
    ]
    assert "preflight" in names
    assert seen == ["pre"]


async def test_real_graph_confirmation_pause_and_resume(clean, recorder):
    from ze_core.routing.types import SubTask

    telemetry, _ = recorder
    h.calls.clear()
    h.register_tools()
    client = h.scripted_client(
        (None, [h.tc("c1", "delete_event", event_id="e1")]), ("Deleted.", None)
    )
    h.register_agent("calendar", client, ["delete_event"])
    # compiled_graph builds through graph_builder, so these nodes are the real wrapped ones.
    graph = h.compiled_graph([SubTask("calendar", "do it")])
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("delete my 3pm"), cfg)
    state = await graph.aget_state(cfg)
    assert state.next
    telemetry.pause()
    telemetry.begin_resumed_run()
    await graph.ainvoke(Command(resume={"choice": "approve"}), cfg)
    runs = [(s.name, s.run) for s in telemetry.stages]
    assert runs.count(("await_write_confirmation", 1)) == 1
    assert runs.count(("await_write_confirmation", 2)) == 1
    assert ("record_trace", 2) in runs
    assert ("preprocess", 1) in runs and ("preprocess", 2) not in runs
