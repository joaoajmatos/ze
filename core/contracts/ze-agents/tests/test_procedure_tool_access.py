"""Procedure tool-name narrowing in `BaseAgent.agentic_loop()` (Phase 139)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.registry import clear_registry
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext, AgentResult


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    yield
    clear_registry()
    clear_tool_registry()


def _ctx(**kwargs) -> AgentContext:
    return AgentContext(session_id="s1", prompt="hello", intent="read", **kwargs)


def _agent(tools: list[str]) -> BaseAgent:
    class _A(BaseAgent):
        name = "test"
        description = "test agent"

        async def run(self, ctx: AgentContext) -> AgentResult:
            return AgentResult(agent=self.name, response="ok")

    a = _A()
    a.tools = tools
    return a


def _client(response=("done", None)) -> MagicMock:
    client = MagicMock()
    client.complete_with_tools = AsyncMock(return_value=response)
    client.complete = AsyncMock(return_value="fallback text")
    return client


def _register(name: str) -> None:
    async def _impl(x: str = "") -> str:
        return "ok"

    _impl.__name__ = name
    tool(access=ToolAccess.READ, description=name)(_impl)


class TestProcedureToolNarrowing:
    async def test_procedure_restriction_intersects_never_unions(self):
        _register("tool_a")
        _register("tool_b")
        a = _agent(["tool_a", "tool_b"])
        client = _client()

        await a.agentic_loop(
            _ctx(procedure_tool_names=["tool_a", "tool_c"]),
            client,
            [],
            system="s",
        )

        schemas = client.complete_with_tools.call_args[1]["tools"]
        assert {s["function"]["name"] for s in schemas} == {"tool_a"}

    async def test_no_invocation_does_not_narrow_tools(self):
        _register("tool_a")
        _register("tool_b")
        a = _agent(["tool_a", "tool_b"])
        client = _client()

        await a.agentic_loop(_ctx(), client, [], system="s")

        schemas = client.complete_with_tools.call_args[1]["tools"]
        assert {s["function"]["name"] for s in schemas} == {"tool_a", "tool_b"}
