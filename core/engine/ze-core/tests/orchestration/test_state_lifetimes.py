"""Every graph-state field declares its lifetime; the turn reset is generated from them."""

from __future__ import annotations

import asyncio
from typing import Annotated, TypedDict
from unittest.mock import MagicMock

import pytest

from ze_agents.errors import UndeclaredLifetimeError
from ze_agents.lifetime import Input, Run, Thread, Turn, field_lifetimes, turn_reset
from ze_core.orchestration.graph import build_graph
from ze_core.orchestration.state import (
    AgentState,
    build_state_type,
    with_turn_reset,
)

_INPUT = {
    "prompt",
    "session_id",
    "input_modality",
    "voice_input",
    "image_data",
    "image_mime",
}
_THREAD = {"messages", "last_active_at"}

_EXPECTED_RESET = {
    **dict.fromkeys(
        [
            "image_caption",
            "envelope",
            "memory_context",
            "agent_context",
            "agent_result",
            "budget_status",
            "write_confirmation",
            "final_response",
            "error",
            "conductor_hint",
            "routing_hints",
            "screen_note",
            "screen_trace",
            "screen_subject_line",
            "message_trace",
            "tier",
            "skill_matches",
        ],
        None,
    ),
    **dict.fromkeys(
        [
            "subtask_results",
            "completed_subtask_indexes",
            "parked_subtasks",
            "write_decisions",
            "write_outcomes",
            "components",
            "preset_components",
            "correlations",
            "judgments",
            "loop_offer_ids",
            "pre_approved_writes",
            "conductor_ledgers",
            "procedure_invocations",
        ],
        [],
    ),
    "blocked": False,
    "budget_approved": False,
    "resume_recap_applied": False,
    "open_items_query": False,
    "write_rounds": 0,
    "conductor_delegate_total": 0,
    "conductor_delegate_counts": {},
}


def test_every_agent_state_key_declares_a_lifetime() -> None:
    lifetimes = field_lifetimes(AgentState)
    assert {k for k, v in lifetimes.items() if isinstance(v, Input)} == _INPUT
    assert {k for k, v in lifetimes.items() if isinstance(v, Thread)} == _THREAD
    assert all(isinstance(v, (Turn, Input, Thread)) for v in lifetimes.values())


def test_reset_values_are_the_declared_table() -> None:
    assert turn_reset(AgentState) == _EXPECTED_RESET


def test_the_fields_phase_200_added_to_the_reset_are_covered() -> None:
    reset = turn_reset(AgentState)
    for key in (
        "resume_recap_applied",
        "open_items_query",
        "loop_offer_ids",
        "pre_approved_writes",
    ):
        assert key in reset


def test_procedure_matches_is_cut_from_state() -> None:
    assert "procedure_matches" not in field_lifetimes(AgentState)
    assert "conductor_ledger" not in field_lifetimes(AgentState)


class _Unmarked(TypedDict, total=False):
    stray_field: list


def _plugin(extension) -> MagicMock:
    plugin = MagicMock()
    plugin.state_extensions.return_value = extension
    plugin.pre_route_node.return_value = None
    return plugin


def test_an_unmarked_extension_field_fails_state_build() -> None:
    with pytest.raises(UndeclaredLifetimeError, match="stray_field"):
        build_state_type([_plugin(_Unmarked)])


def test_an_unmarked_extension_field_fails_graph_build() -> None:
    with pytest.raises(UndeclaredLifetimeError, match="stray_field"):
        build_graph(MagicMock(), plugins=[_plugin(_Unmarked)])


class _Marked(TypedDict, total=False):
    plugin_turn: Annotated[list, Turn(factory=list)]
    plugin_run: Annotated[int, Run("kept across a run")]


def test_a_marked_extension_joins_the_merged_reset() -> None:
    merged = build_state_type([_plugin(_Marked)])
    reset = turn_reset(merged)
    assert reset["plugin_turn"] == []
    assert "plugin_run" not in reset
    assert reset["judgments"] == []


def test_with_turn_reset_starts_from_the_reset_and_lets_the_node_win() -> None:
    async def node(state, config):
        return {"judgments": ["kept"], "prompt": "step prompt"}

    wrapped = with_turn_reset(node, AgentState)
    result = asyncio.run(wrapped({}, {}))
    assert result["judgments"] == ["kept"]
    assert result["prompt"] == "step prompt"
    assert result["components"] == [] and result["tier"] is None
    assert "messages" not in result


def test_with_turn_reset_accepts_a_sync_node() -> None:
    wrapped = with_turn_reset(lambda state, config: {"error": "x"}, AgentState)
    assert asyncio.run(wrapped({}, {}))["error"] == "x"
