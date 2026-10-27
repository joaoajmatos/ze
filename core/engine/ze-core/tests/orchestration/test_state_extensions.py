from typing import Annotated, TypedDict, get_type_hints
from unittest.mock import MagicMock

from ze_agents.lifetime import Run
from ze_core.orchestration.state import AgentState, build_state_type


class _PlainExtension(TypedDict, total=False):
    workflow_id: Annotated[str, Run("a workflow run's id")]
    visit_counts: Annotated[dict[str, int], Run("kept across a run")]


def test_plain_typeddict_extension_keeps_agent_state_fields():
    plugin = MagicMock()
    plugin.state_extensions.return_value = _PlainExtension

    merged = build_state_type([plugin])

    hints = get_type_hints(merged)
    assert set(get_type_hints(AgentState)) <= set(hints)
    assert {"workflow_id", "visit_counts"} <= set(hints)


def test_no_extensions_returns_agent_state():
    plugin = MagicMock()
    plugin.state_extensions.return_value = None
    assert build_state_type([plugin]) is AgentState
