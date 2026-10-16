"""TierTrace — stored-trace round trip, checkpoint serde and the per-turn reset."""

from __future__ import annotations

from dataclasses import asdict

import pytest
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer  # type: ignore[import]

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

