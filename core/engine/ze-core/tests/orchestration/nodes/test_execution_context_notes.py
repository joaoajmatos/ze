"""Prompt notes set by fetch_context must reach the agent that execute_tool runs.

execute_tool builds a fresh AgentContext per subtask; a note not carried over
never reaches the system prompt (the open-query reroute answered "nothing open").
"""

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


def _register(name: str, seen: list):
    class _A:
        async def run(self, ctx: AgentContext) -> AgentResult:
            seen.append(
                (
                    name,
                    ctx.open_priorities_note,
                    ctx.resume_recap,
                    ctx.screen_context_note,
                )
            )
            return AgentResult(agent=name, response=name)

    _A.__name__ = f"Agent_{name}"
    _A.name = name
    _A.description = name
    _A.enabled = True
    _A.timeout = 30
    agent(_A)
    register_instance(name, _A())


def _state(*agents: str) -> dict:
    envelope = RoutingEnvelope(
        primary_agent=agents[0],
        confidence=1.0,
        score_gap=0.0,
        routing_method="open_query",
        is_compound=len(agents) > 1,
        subtasks=[
            SubTask(agent=a, prompt="what's open") for a in agents
        ],
        requires_synthesis=len(agents) > 1,
    )
    ctx = AgentContext(
        session_id="s1",
        prompt="what's open",
        memory=MemoryContext(),
        messages=[],
    )
    ctx.open_priorities_note = "[Open priorities]\n- Run a marathon"
    ctx.resume_recap = "[Recap] last time"
    ctx.screen_context_note = "[Screen] workflow 1"
    return {
        "envelope": envelope,
        "agent_context": ctx,
        "image_data": None,
    }


_NOTES = (
    "[Open priorities]\n- Run a marathon",
    "[Recap] last time",
    "[Screen] workflow 1",
)


async def test_single_agent_receives_the_prompt_notes():
    seen: list = []
    _register("companion", seen)
    await execute_tool(_state("companion"), {"configurable": {"thread_id": "s1"}})
    assert seen == [("companion", *_NOTES)]


async def test_compound_subtasks_receive_the_prompt_notes():
    seen: list = []
    _register("calendar", seen)
    _register("messenger", seen)
    await execute_tool(
        _state("calendar", "messenger"), {"configurable": {"thread_id": "s1"}}
    )
    assert sorted(seen) == [("calendar", *_NOTES), ("messenger", *_NOTES)]
