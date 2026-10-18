"""Companion shows the composed answers through show_slipping / show_decisions / show_topic."""

from unittest.mock import AsyncMock

import ze_priority
import ze_priority.compose.tools  # noqa: F401 — registers the show_* tools
from ze_agents.tool import ToolAccess, get_tool
from ze_personal.agents.companion.agent import _AGENT_INSTRUCTIONS, CompanionAgent

from ze_agents.settings import Settings
from ze_agents.types import AgentContext
from ze_sdk.memory import MemoryContext


def make_agent() -> CompanionAgent:
    return CompanionAgent(
        openrouter_client=AsyncMock(),
        settings=Settings(
            openrouter_api_key="test-key",
            database_url="postgresql://ze:ze@localhost:5432/ze",
        ),
        person_store=AsyncMock(),
        outreach_log=None,
        memory_store=AsyncMock(),
    )


def make_ctx(prompt: str) -> AgentContext:
    return AgentContext(
        session_id="s1",
        prompt=prompt,
        memory=MemoryContext(),
        messages=[{"role": "user", "content": prompt}],
    )


SHOW_TOOLS = ("show_slipping", "show_decisions", "show_topic")


def test_companion_lists_the_three_composed_answer_tools():
    ze_priority.import_agent_modules()
    assert set(SHOW_TOOLS) <= set(CompanionAgent.tools)
    for name in SHOW_TOOLS:
        assert get_tool(name).access is ToolAccess.READ


def test_instructions_say_when_to_call_them_and_to_ground_the_sentence():
    text = _AGENT_INSTRUCTIONS
    for name in SHOW_TOOLS:
        assert name in text
    assert "one or two sentences from the returned summary only" in text
    assert "never list every card" in text
    assert "sources_failed" in text


def test_tool_deps_carry_the_memory_and_notification_stores():
    assert set(make_agent().tool_deps()) == {"memory_store", "notification_store"}


async def test_run_passes_the_composer_and_the_preset_to_the_tool_loop():
    composer = object()
    agent = make_agent()
    agent._world_composer = composer
    agent.agentic_loop = AsyncMock(return_value=("ok", []))
    ctx = make_ctx("What's slipping?")
    ctx.preset = "slipping"

    await agent.run(ctx)

    deps = agent.agentic_loop.await_args.kwargs["deps"]
    assert deps["world_composer"] is composer
    assert deps["preset"] == "slipping"
    assert deps["memory_store"] is agent._memory_store


async def test_run_without_a_preset_passes_none():
    agent = make_agent()
    agent.agentic_loop = AsyncMock(return_value=("ok", []))
    await agent.run(make_ctx("hi"))
    assert agent.agentic_loop.await_args.kwargs["deps"]["preset"] is None
