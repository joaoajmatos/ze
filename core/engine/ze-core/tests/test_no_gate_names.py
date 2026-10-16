"""Guards for the intent-based gate hard cut (Phase 181, SC-006/SC-007)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.errors import LoopParked
from ze_agents.registry import clear_registry
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext

ROOT = Path(__file__).resolve().parents[4]
_ROOTS = ("core", "plugins", "apps", "packages", "integrations")
_REMOVED = re.compile(
    r"\bGateDecision\b|\bIntent\(|\bMode\.|intents = \{|default_mode\b|_primary_intent"
    r"|CapabilityGate|session_overrides|capability_overrides|ToolConfirmationRequired"
    r"|tool_interrupt_fn|workspace_confirmed|is_draft"
)


def _python_files():
    for top in _ROOTS:
        for path in (ROOT / top).rglob("*.py"):
            parts = set(path.parts) | {p for p in path.parts}
            if ".venv" in parts or "node_modules" in parts or "migrations" in parts:
                continue
            if path.name == Path(__file__).name or "ze-eval" in parts:
                continue
            yield path


def test_removed_gate_names_are_gone() -> None:
    hits = []
    for path in _python_files():
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if _REMOVED.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert hits == []


def test_interrupt_is_imported_only_by_the_execution_node() -> None:
    importers = []
    for path in _python_files():
        text = path.read_text()
        if re.search(r"from langgraph\.types import[^\n]*\binterrupt\b", text):
            importers.append(str(path.relative_to(ROOT)))
    assert importers == ["core/engine/ze-core/ze_core/orchestration/nodes/execution.py"]


@pytest.fixture
def clean():
    clear_registry()
    clear_tool_registry()
    yield
    clear_registry()
    clear_tool_registry()


async def test_a_new_irreversible_write_asks_first_with_no_other_argument(
    clean,
) -> None:
    ran: list[str] = []

    @tool(
        access=ToolAccess.WRITE,
        description="new",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="did a new thing",
    )
    async def brand_new_write(x: str = "") -> str:
        ran.append(x)
        return "ok"

    class _A(BaseAgent):
        name = "any"
        description = "d"
        tools = ["brand_new_write"]

        async def run(self, ctx):  # pragma: no cover
            raise NotImplementedError

    from unittest.mock import AsyncMock, MagicMock

    client = MagicMock()
    client.complete_with_tools = AsyncMock(
        return_value=(
            None,
            [{"id": "c1", "name": "brand_new_write", "arguments": {"x": "1"}}],
        )
    )
    with pytest.raises(LoopParked):
        await _A().agentic_loop(
            AgentContext(session_id="s", prompt="p"), client, [], system="s"
        )
    assert ran == []
