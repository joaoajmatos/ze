"""A preset chip's composition is prepended to the turn's components, and the preset
key reaches every agent context execute_tool builds."""

from unittest.mock import MagicMock

import pytest
from ze_agents.registry import agent, clear_registry, register_instance
from ze_agents.types import AgentContext, AgentResult
from ze_core.orchestration.nodes.execution import execute_tool
from ze_core.routing.types import RoutingEnvelope, SubTask
from ze_memory.types import MemoryContext

PRESET = [
    {"type": "headline", "text": "2 SLIPPING"},
    {"type": "claim_card", "title": "x"},
]


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def _register(name: str, seen: list):
    class _A:
        async def run(self, ctx: AgentContext) -> AgentResult:
            seen.append((name, ctx.preset))
            return AgentResult(agent=name, response=name)

    _A.__name__ = f"Agent_{name}"
    _A.name = name
    _A.description = name
    _A.enabled = True
    _A.timeout = 30
    agent(_A)
    register_instance(name, _A())


def _state(*agents: str, preset: str | None = "slipping", components=PRESET) -> dict:
    envelope = RoutingEnvelope(
        primary_agent=agents[0],
        confidence=1.0,
        score_gap=0.0,
        routing_method="preset",
        is_compound=len(agents) > 1,
        subtasks=[SubTask(agent=a, prompt="what's slipping") for a in agents],
        requires_synthesis=len(agents) > 1,
    )
    ctx = AgentContext(
        session_id="s1", prompt="what's slipping", memory=MemoryContext(), messages=[]
    )
    ctx.preset = preset
    return {
        "envelope": envelope,
        "agent_context": ctx,
        "image_data": None,
        "preset_components": list(components),
    }


def _config(agent_components=None) -> dict:
    hook = None
    if agent_components is not None:
        hook = MagicMock()
        hook.pop_components = MagicMock(return_value=list(agent_components))
    return {"configurable": {"thread_id": "s1", "component_hook": hook}}


async def test_single_agent_components_follow_the_preset():
    seen: list = []
    _register("companion", seen)
    agent_card = {"type": "text", "content": "from the agent"}

    result = await execute_tool(_state("companion"), _config([agent_card]))

    assert result["components"] == [*PRESET, agent_card]
    assert seen == [("companion", "slipping")]


async def test_single_agent_without_a_preset_has_only_its_own_components():
    seen: list = []
    _register("companion", seen)
    agent_card = {"type": "text", "content": "x"}

    result = await execute_tool(
        _state("companion", preset=None, components=[]), _config([agent_card])
    )

    assert result["components"] == [agent_card]
    assert seen == [("companion", None)]


async def test_compound_turn_returns_the_preset_components_itself():
    seen: list = []
    _register("calendar", seen)
    _register("messenger", seen)

    result = await execute_tool(_state("calendar", "messenger"), _config([]))

    assert result["components"] == PRESET
    assert sorted(seen) == [("calendar", "slipping"), ("messenger", "slipping")]


async def test_missing_preset_components_key_is_an_empty_list():
    seen: list = []
    _register("companion", seen)
    state = _state("companion")
    del state["preset_components"]
    result = await execute_tool(state, _config([]))
    assert result["components"] == []
