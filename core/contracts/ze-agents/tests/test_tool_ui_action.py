"""`@tool(ui_action=True, done_phrase=...)` declarations (Phase 191a)."""

from __future__ import annotations

import pytest

from ze_agents.errors import AgentConfigError
from ze_agents.registry import clear_registry
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, clear_tool_registry, get_tool, tool


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    yield
    clear_registry()
    clear_tool_registry()


def test_ui_action_and_done_phrase_stored_on_spec() -> None:
    @tool(
        access=ToolAccess.WRITE,
        description="d",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="marked a source as read",
        ui_action=True,
        done_phrase="Marked as read.",
    )
    async def mark_read(source_id: str) -> str:
        return "ok"

    spec = get_tool("mark_read")
    assert spec.ui_action is True
    assert spec.done_phrase == "Marked as read."


def test_defaults_are_off() -> None:
    @tool(
        access=ToolAccess.WRITE,
        description="d",
        reversibility=ToolReversibility.IRREVERSIBLE,
    )
    async def plain(x: str) -> str:
        return "ok"

    spec = get_tool("plain")
    assert spec.ui_action is False
    assert spec.done_phrase is None


def test_read_tool_cannot_be_ui_action() -> None:
    with pytest.raises(AgentConfigError, match="ui_action"):

        @tool(access=ToolAccess.READ, description="d", ui_action=True)
        async def look(x: str) -> str:
            return "ok"


def test_read_tool_cannot_declare_done_phrase() -> None:
    with pytest.raises(AgentConfigError, match="done_phrase"):

        @tool(access=ToolAccess.READ, description="d", done_phrase="Done.")
        async def look2(x: str) -> str:
            return "ok"
