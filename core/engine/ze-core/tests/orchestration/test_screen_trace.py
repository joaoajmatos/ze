"""ScreenTrace — stored round trip, record_trace copy, partial frame."""

from __future__ import annotations

from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from ze_core.orchestration.state import AgentState
from ze_core.conversation.messages.store import _parse_trace
from ze_core.conversation.messages.types import (
    MessageTrace,
    ScreenResolverTrace,
    ScreenTrace,
)

RAW = {
    "origin": "chat_about",
    "place": "doing",
    "route": "/doing/workflows/w1",
    "subject": ["Workflow · Weekly report"],
    "selection_count": 1,
    "visible_count": 13,
    "canvas_count": 0,
    "focused_module": "Workflows",
    "captured_at": "2026-10-17T14:02:11+00:00",
    "note_chars": 812,
    "invalid": ["unknown key: screen"],
    "resolvers": [
        {"kind": "workflow", "id": "w1", "status": "ok", "ms": 14},
        {"kind": "goal", "id": "g7", "status": "cut", "ms": 0},
    ],
}


def _trace(screen: ScreenTrace | None) -> MessageTrace:
    return MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.2,
        is_compound=False,
        subtasks=["companion"],
        screen=screen,
    )


def test_screen_defaults_to_none_and_old_traces_parse():
    assert _trace(None).screen is None
    data = asdict(_trace(None))
    data.pop("screen")
    assert _parse_trace(data).screen is None


def test_stored_trace_round_trips_screen():
    screen = ScreenTrace.from_dict(RAW)
    assert screen.resolvers[1] == ScreenResolverTrace("goal", "g7", "cut", 0)
    assert _parse_trace(asdict(_trace(screen))).screen == screen


def test_from_dict_ignores_unknown_keys_and_junk_resolvers():
    screen = ScreenTrace.from_dict(
        {
            **RAW,
            "future": 1,
            "resolvers": [5, {"kind": "a", "id": "b", "status": "ok", "zzz": 1}],
        }
    )
    assert [r.kind for r in screen.resolvers] == ["a"]


async def test_record_trace_copies_the_screen_trace():
    from ze_core.orchestration.nodes.trace import record_trace

    envelope = SimpleNamespace(
        primary_agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.2,
        is_compound=False,
        subtasks=[],
    )
    state = {"envelope": envelope, "screen_trace": RAW}
    trace = (await record_trace(state, {"configurable": {}}))["message_trace"]
    assert trace.screen == ScreenTrace.from_dict(RAW)
    none = (await record_trace({"envelope": envelope}, {"configurable": {}}))[
        "message_trace"
    ]
    assert none.screen is None
    junk = (
        await record_trace(
            {"envelope": envelope, "screen_trace": "oops"}, {"configurable": {}}
        )
    )["message_trace"]
    assert junk.screen is None


async def _stream(events):
    for event in events:
        yield event


async def test_partial_trace_update_carries_the_screen():
    from ze_agents.interface.types import RawInput
    from ze_core.conversation import invoke_raw_turn

    graph = MagicMock()
    graph.name = "LangGraph"
    graph.astream_events = lambda *a, **kw: _stream(
        [
            {
                "event": "on_chain_end",
                "name": "resolve_screen",
                "data": {"output": {"screen_trace": RAW}},
            },
            {
                "event": "on_chain_end",
                "name": "LangGraph",
                "data": {"output": {"final_response": "ok", "error": None}},
            },
        ]
    )
    graph.aget_state = AsyncMock(return_value=MagicMock(next=()))
    interface = MagicMock()
    interface.send_trace_partial = AsyncMock()
    container = MagicMock()
    container.graph = graph
    container.state_type = AgentState
    container.interface = interface
    container._build_config = MagicMock(return_value={"configurable": {}})

    await invoke_raw_turn(container, "42", RawInput(text="hello"))

    partials = [c.args[1] for c in interface.send_trace_partial.call_args_list]
    assert {"screen": RAW} in partials
