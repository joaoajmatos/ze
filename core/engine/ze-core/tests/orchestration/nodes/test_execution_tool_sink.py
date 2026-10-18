"""execute_tool puts the turn's tool sink on every AgentContext it builds (187b)."""

from __future__ import annotations

import pytest

from ze_agents.registry import agent, clear_registry, register_instance
from ze_agents.types import AgentContext, AgentResult
from ze_core.orchestration.nodes.execution import execute_tool
from ze_core.routing.types import RoutingEnvelope, SubTask
from ze_memory.types import MemoryContext


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def _register(name: str, seen: dict) -> None:
    class _A:
        async def run(self, ctx: AgentContext) -> AgentResult:
            seen[name] = ctx.tool_sink
            return AgentResult(agent=name, response="ok")

    _A.__name__ = f"Agent_{name}"
    _A.name = name
    _A.description = name
    _A.enabled = True
    _A.timeout = 30
    agent(_A)
    inst = object.__new__(_A)
    inst.run = _A.run.__get__(inst, _A)
    register_instance(name, inst)


def _state(names: list[str], compound: bool) -> dict:
    return {
        "envelope": RoutingEnvelope(
            primary_agent=names[0],
            confidence=0.9,
            score_gap=0.3,
            routing_method="embedding",
            is_compound=compound,
            subtasks=[SubTask(agent=n, prompt="p") for n in names],
            requires_synthesis=compound,
        ),
        "agent_context": AgentContext(
            session_id="s", prompt="p", memory=MemoryContext(), messages=[]
        ),
        "image_data": None,
    }


async def test_single_agent_gets_the_sink() -> None:
    seen: dict = {}
    _register("a", seen)

    def sink(call):
        return None

    await execute_tool(_state(["a"], False), {"configurable": {"tool_sink": sink}})
    assert seen["a"] is sink


async def test_compound_subtasks_get_the_sink() -> None:
    seen: dict = {}
    _register("a", seen)
    _register("b", seen)

    def sink(call):
        return None

    await execute_tool(_state(["a", "b"], True), {"configurable": {"tool_sink": sink}})
    assert seen == {"a": sink, "b": sink}


async def test_no_sink_configured_is_none() -> None:
    seen: dict = {}
    _register("a", seen)
    await execute_tool(_state(["a"], False), {"configurable": {}})
    assert seen["a"] is None
