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
_ROOTS = ("core", "plugins", "apps", "packages", "integrations", "eval")
_REMOVED = re.compile(
    r"\bGateDecision\b|\bIntent\(|\bMode\.|intents = \{|default_mode\b|_primary_intent"
    r"|CapabilityGate|session_overrides|capability_overrides|ToolConfirmationRequired"
    r"|tool_interrupt_fn|workspace_confirmed|is_draft|DRAFT_ONLY|AWAIT_CONFIRMATION"
    r"|\bcapability_check\b|\bdraft_response\b|\bawait_confirmation\b"
    r"|\bawait_subtask_confirmation\b"
)
_SKIP_PARTS = {".venv", "node_modules", "migrations", ".pytest_cache", "results"}


def _files(*patterns: str):
    for top in _ROOTS:
        for pattern in patterns:
            for path in (ROOT / top).rglob(pattern):
                if _SKIP_PARTS & set(path.parts) or path.name == Path(__file__).name:
                    continue
                yield path


def _python_files():
    return _files("*.py")


def test_removed_gate_names_are_gone() -> None:
    hits = []
    for path in _files("*.py", "*.yaml", "*.yml"):
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
