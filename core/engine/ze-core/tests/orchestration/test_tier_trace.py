"""TierTrace — stored-trace round trip, checkpoint serde and the per-turn reset."""

from __future__ import annotations

from dataclasses import asdict

import pytest
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer  # type: ignore[import]

from ze_core.orchestration.state import AgentState
from ze_core.checkpoint_serde import build_checkpoint_serde
from ze_core.conversation.messages.store import _parse_trace
from ze_core.conversation.messages.types import MessageTrace, TierTrace
from ze_core.conversation.turn import make_graph_input_from_raw_text


def _trace(tier: TierTrace | None) -> MessageTrace:
    return MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.2,
        is_compound=False,
        subtasks=["companion"],
        tier=tier,
    )


def test_tier_defaults_to_none() -> None:
    assert _trace(None).tier is None


def test_stored_trace_round_trips_tier() -> None:
    tier = TierTrace(
        agent="companion", tier="simple", decided_by="system_one", model="haiku"
    )
    trace = _trace(tier)
    assert _parse_trace(asdict(trace)) == trace


def test_old_trace_without_tier_parses_to_none() -> None:
    data = asdict(_trace(None))
    data.pop("tier")
    assert _parse_trace(data).tier is None


def test_tier_survives_checkpoint_serde() -> None:
    serde: JsonPlusSerializer = build_checkpoint_serde(plugins=[])
    tier = TierTrace(agent="research", tier="full", decided_by="off", model="sonnet")
    restored = serde.loads_typed(serde.dumps_typed(tier))
    assert restored == tier


def test_new_turn_clears_the_previous_tier() -> None:
    state = make_graph_input_from_raw_text("hello", "s1")
    assert state["tier"] is None


_DECIDED_BY = [
    ("simple", "system_one"),
    ("full", "system_one"),
    ("full", "off"),
    ("full", "uncalibrated"),
    ("full", "skip"),
    ("full", "invalid_answer"),
    ("full", "compound"),
    ("full", "no_simple_model"),
]


@pytest.mark.parametrize(("tier", "decided_by"), _DECIDED_BY)
async def test_record_trace_copies_the_tier(tier, decided_by):
    from types import SimpleNamespace

    from ze_core.orchestration.nodes.trace import record_trace

    record = TierTrace("companion", tier, decided_by, "some/model")
    state = {
        "envelope": SimpleNamespace(
            primary_agent="companion",
            routing_method="embedding",
            confidence=0.9,
            score_gap=0.2,
            is_compound=False,
            subtasks=[],
        ),
        "tier": record,
    }
    trace = (await record_trace(state, {"configurable": {}}))["message_trace"]
    assert trace.tier == record


async def test_record_trace_without_a_tier_leaves_it_none():
    from types import SimpleNamespace

    from ze_core.orchestration.nodes.trace import record_trace

    state = {
        "envelope": SimpleNamespace(
            primary_agent="companion",
            routing_method="embedding",
            confidence=0.9,
            score_gap=0.2,
            is_compound=False,
            subtasks=[],
        ),
    }
    trace = (await record_trace(state, {"configurable": {}}))["message_trace"]
    assert trace.tier is None


async def _stream(events):
    for event in events:
        yield event


@pytest.mark.parametrize(("tier", "decided_by"), _DECIDED_BY)
async def test_partial_trace_update_carries_the_tier(tier, decided_by):
    from unittest.mock import AsyncMock, MagicMock

    from ze_agents.interface.types import RawInput
    from ze_core.conversation import invoke_raw_turn

    record = TierTrace("companion", tier, decided_by, "some/model")
    graph = MagicMock()
    graph.name = "LangGraph"
    graph.astream_events = lambda *a, **kw: _stream(
        [
            {
                "event": "on_chain_end",
                "name": "choose_tier",
                "data": {"output": {"tier": record}},
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
    assert {"tier": asdict(record)} in partials


async def test_no_tier_frame_when_the_node_returns_nothing():
    from unittest.mock import AsyncMock, MagicMock

    from ze_agents.interface.types import RawInput
    from ze_core.conversation import invoke_raw_turn

    graph = MagicMock()
    graph.name = "LangGraph"
    graph.astream_events = lambda *a, **kw: _stream(
        [
            {"event": "on_chain_end", "name": "choose_tier", "data": {"output": {}}},
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

    interface.send_trace_partial.assert_not_called()
