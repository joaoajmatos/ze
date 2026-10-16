import asyncio
from unittest.mock import AsyncMock

import pytest

from ze_agents.errors import AgentTimeoutError
from ze_memory.types import MemoryContext
from ze_agents.registry import agent, clear_registry, register_instance
from ze_core.orchestration.nodes.execution import (
    execute_tool,
)
from ze_agents.types import AgentContext, AgentResult
from ze_core.routing.types import RoutingEnvelope, SubTask


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def _make_agent_class(name: str, response: str = "ok", timeout: int = 30):
    class _A:
        async def run(self, ctx: AgentContext) -> AgentResult:
            return AgentResult(agent=name, response=response)

    _A.__name__ = f"Agent_{name}"
    _A.name = name
    _A.description = f"Agent {name}"
    _A.enabled = True
    _A.timeout = timeout
    return _A


def _register_and_wire(name: str, response: str = "ok", timeout: int = 30):
    cls = _make_agent_class(name, response, timeout)
    agent(cls)
    instance = object.__new__(cls)
    instance.run = cls.run.__get__(instance, cls)
    instance.stream = AsyncMock(side_effect=NotImplementedError)
    register_instance(name, instance)
    return instance


def _envelope(
    agent_name: str,
    is_compound: bool = False,
    is_sequential: bool = False,
    subtasks: list | None = None,
) -> RoutingEnvelope:
    if subtasks is None:
        subtasks = [SubTask(agent=agent_name, prompt="do it")]
    return RoutingEnvelope(
        primary_agent=agent_name,
        confidence=0.9,
        score_gap=0.3,
        routing_method="embedding",
        is_compound=is_compound,
        subtasks=subtasks,
        requires_synthesis=is_compound and not is_sequential,
        is_sequential=is_sequential,
    )


def _ctx(agent_name: str = "a") -> AgentContext:
    return AgentContext(
        session_id="s1",
        prompt="do it",
        memory=MemoryContext(),
        messages=[],
    )


# ── execute_tool ──────────────────────────────────────────────────────────────


class TestExecuteTool:
    async def test_single_agent_result(self):
        _register_and_wire("a", response="hello")
        state = {
            "envelope": _envelope("a"),
            "agent_context": _ctx("a"),
            "image_data": None,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert result["agent_result"].response == "hello"
        assert result["subtask_results"] == []

    async def test_missing_context_returns_error(self):
        state = {
            "envelope": None,
            "agent_context": None,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert "error" in result

    async def test_compound_parallel(self):
        _register_and_wire("alpha", response="r1")
        _register_and_wire("beta", response="r2")
        subtasks = [
            SubTask(agent="alpha", prompt="p1"),
            SubTask(agent="beta", prompt="p2"),
        ]
        env = _envelope("alpha", is_compound=True, subtasks=subtasks)
        state = {
            "envelope": env,
            "agent_context": _ctx("alpha"),
            "image_data": None,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert result["agent_result"] is None
        assert len(result["subtask_results"]) == 2
        responses = {r.response for r in result["subtask_results"]}
        assert responses == {"r1", "r2"}
        assert result["parked_subtasks"] == []

    async def test_compound_single_subtask_uses_agent_result(self):
        _register_and_wire("news", response="headlines")
        subtasks = [SubTask(agent="news", prompt="search trump health")]
        env = _envelope("news", is_compound=True, subtasks=subtasks)
        state = {
            "envelope": env,
            "agent_context": _ctx("news"),
            "image_data": None,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert result["agent_result"].response == "headlines"
        assert result["subtask_results"] == []

    async def test_compound_sequential_flag_still_fans_out(self):
        """Sequential execute loop is gone; compound still gathers in parallel."""
        _register_and_wire("alpha", response="r1")
        _register_and_wire("beta", response="r2")
        subtasks = [
            SubTask(agent="alpha", prompt="p1"),
            SubTask(agent="beta", prompt="p2"),
        ]
        env = _envelope(
            "alpha", is_compound=True, is_sequential=True, subtasks=subtasks
        )
        state = {
            "envelope": env,
            "agent_context": _ctx("alpha"),
            "image_data": None,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert result["agent_result"] is None
        assert len(result["subtask_results"]) == 2

    async def test_timeout_raises(self):
        cls = _make_agent_class("slow", timeout=0)

        async def slow_run(self, ctx):
            await asyncio.sleep(10)
            return AgentResult(agent="slow", response="late")

        cls.run = slow_run
        agent(cls)
        instance = object.__new__(cls)
        instance.run = slow_run.__get__(instance, cls)
        register_instance("slow", instance)

        state = {
            "envelope": _envelope("slow"),
            "agent_context": _ctx("slow"),
            "image_data": None,
        }
        with pytest.raises(AgentTimeoutError):
            await execute_tool(state, {"configurable": {}})


class TestPreflight:
    async def test_all_agents_disabled_blocks(self):
        from ze_core.orchestration.nodes.execution import preflight

        cls = _make_agent_class("off")
        cls.enabled = False
        agent(cls)
        result = await preflight({"envelope": _envelope("off")}, {"configurable": {}})
        assert result == {"blocked": True}

    async def test_no_subtasks_blocks(self):
        from ze_core.orchestration.nodes.execution import preflight

        env = _envelope("a", subtasks=[])
        assert await preflight({"envelope": env}, {"configurable": {}}) == {
            "blocked": True
        }

    async def test_enabled_agent_without_budget_checker_passes(self):
        from ze_core.orchestration.nodes.execution import preflight

        _register_and_wire("a")
        result = await preflight(
            {"envelope": _envelope("a"), "session_id": "s1"}, {"configurable": {}}
        )
        assert result == {}
