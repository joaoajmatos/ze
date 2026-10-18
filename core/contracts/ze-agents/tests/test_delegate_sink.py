"""A delegate's calls reach the turn's tool sink and keep their ids (187b)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.delegate import run_delegate
from ze_agents.nested_tools import flatten_tool_calls
from ze_agents.registry import agent, clear_registry, register_instance
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext, AgentResult, ToolCall


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()

    async def list_events() -> str:
        return "events"

    tool(access=ToolAccess.READ, description="list")(list_events)
    yield
    clear_registry()
    clear_tool_registry()


def _register(name: str) -> None:
    client = MagicMock()
    client.complete_with_tools = AsyncMock(
        side_effect=[
            (None, [{"id": "call_0", "name": "list_events", "arguments": {}}]),
            ("done", None),
        ]
    )

    async def _run(self, ctx: AgentContext) -> AgentResult:
        text, tcs = await self.agentic_loop(
            ctx, client, list(ctx.messages), system="s", tool_names=["list_events"]
        )
        return AgentResult(agent=self.name, response=text, tool_calls=tcs)

    cls = type(
        f"_{name}",
        (BaseAgent,),
        {"name": name, "description": name, "tools": [], "run": _run},
    )
    agent(cls)
    register_instance(name, cls())


async def _delegate(to: str, seen: list[ToolCall]) -> ToolCall:
    ctx = AgentContext(session_id="s", prompt="p", tool_sink=seen.append)
    return await run_delegate(
        {"agent_name": to, "objective": "do it"}, ctx, 0, caller_name="companion"
    )


async def test_specialist_calls_reach_the_sink() -> None:
    _register("calendar")
    seen: list[ToolCall] = []
    await _delegate("calendar", seen)
    assert [c.tool_name for c in seen] == ["list_events"]
    assert seen[0].agent == "calendar" and seen[0].started_at is not None


async def test_nested_dict_and_flatten_keep_call_id_and_started_at() -> None:
    _register("calendar")
    seen: list[ToolCall] = []
    outer = await _delegate("calendar", seen)
    nested = outer.result["tool_calls"]
    assert nested[0]["call_id"] == seen[0].call_id
    assert nested[0]["started_at"] == seen[0].started_at
    flat = flatten_tool_calls([outer])
    inner = [c for c in flat if c.tool_name == "list_events"]
    assert inner[0].call_id == seen[0].call_id
    assert inner[0].started_at == seen[0].started_at


async def test_two_delegates_with_colliding_provider_ids_get_distinct_ids() -> None:
    _register("calendar")
    _register("messenger")
    seen: list[ToolCall] = []
    await _delegate("calendar", seen)
    await _delegate("messenger", seen)
    assert len({c.call_id for c in seen}) == 2
