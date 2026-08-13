"""Tests for skill-driven tool-name narrowing in `BaseAgent.agentic_loop()` (FR-008).

The full `BaseAgent` suite (call_tool, hooks, loop mechanics) lives at
`core/ze-core/tests/orchestration/test_base_agent.py`. This file is scoped to
Phase 114 User Story 2's tool-narrowing intersection behaviour: a skill's
`allowed_tools` may only ever narrow — never expand — an agent's own `tools`.
"""

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


def _ctx(skill_tool_names: list[str] | None = None) -> AgentContext:
    return AgentContext(
        session_id="s1",
        prompt="hello",
        intent="read",
        skill_tool_names=skill_tool_names,
    )


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


class TestSkillToolNarrowing:
    async def test_no_skill_restriction_uses_agent_tools_unchanged(self):
        _register("tool_a")
        _register("tool_b")
        a = _agent(["tool_a", "tool_b"])
        client = _client()

        await a.agentic_loop(_ctx(skill_tool_names=None), client, [], system="s")

        schemas = client.complete_with_tools.call_args[1]["tools"]
        assert {s["function"]["name"] for s in schemas} == {"tool_a", "tool_b"}

    async def test_skill_restriction_intersects_never_unions(self):
        _register("tool_a")
        _register("tool_b")
        a = _agent(["tool_a", "tool_b"])
        client = _client()

        # Skill also names "tool_c", which the agent doesn't have — must have
        # no effect (spec Edge Cases): only the intersection is used.
        await a.agentic_loop(
            _ctx(skill_tool_names=["tool_a", "tool_c"]), client, [], system="s"
        )

        schemas = client.complete_with_tools.call_args[1]["tools"]
        assert {s["function"]["name"] for s in schemas} == {"tool_a"}

    async def test_multiple_skills_restrictions_are_intersected_together(self):
        """Simulates the match_skills node's own intersection across matched skills
        (skill A allows tool_a+tool_b, skill B allows tool_b+tool_c) — only the
        overlap (tool_b) should ever reach the agent."""
        _register("tool_a")
        _register("tool_b")
        _register("tool_c")
        a = _agent(["tool_a", "tool_b", "tool_c"])
        client = _client()

        combined_restriction = list(
            {"tool_a", "tool_b"} & {"tool_b", "tool_c"}
        )  # == ["tool_b"], mirrors node-level intersection

        await a.agentic_loop(
            _ctx(skill_tool_names=combined_restriction), client, [], system="s"
        )

        schemas = client.complete_with_tools.call_args[1]["tools"]
        assert {s["function"]["name"] for s in schemas} == {"tool_b"}

    async def test_empty_skill_restriction_allows_no_tools(self):
        _register("tool_a")
        a = _agent(["tool_a"])
        client = _client()

        await a.agentic_loop(_ctx(skill_tool_names=[]), client, [], system="s")

        schemas = client.complete_with_tools.call_args[1]["tools"]
        assert schemas == []

    async def test_explicit_tool_names_param_still_gets_narrowed(self):
        """The tool_names= override (used for compound/delegate invocations) is
        narrowed the same way as the agent's default `self.tools`."""
        _register("tool_a")
        _register("tool_b")
        a = _agent(["tool_a", "tool_b"])
        client = _client()

        await a.agentic_loop(
            _ctx(skill_tool_names=["tool_a"]),
            client,
            [],
            system="s",
            tool_names=["tool_a", "tool_b"],
        )

        schemas = client.complete_with_tools.call_args[1]["tools"]
        assert {s["function"]["name"] for s in schemas} == {"tool_a"}
