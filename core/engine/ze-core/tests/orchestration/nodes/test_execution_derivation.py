"""execute_tool derives each child context from the turn's context (phase 200, US1).

The turn context carries Lisbon time and the user message id. A routed agent and every
compound subtask must see both; only the single path streams tokens.
"""

from __future__ import annotations

import pytest

from ze_agents.base_agent import BaseAgent
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


class _PromptBuilder(BaseAgent):
    async def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError


def _register(name: str, seen: dict) -> None:
    class _A:
        async def run(self, ctx: AgentContext) -> AgentResult:
            prompt_line = (
                _PromptBuilder()
                ._build_system_prompt("instructions", ctx)
                .splitlines()[0]
            )
            seen[name] = {
                "timezone": ctx.timezone,
                "prompt_line": prompt_line,
                "message_id": ctx.extensions.get("user_message_id"),
                "token_sink": ctx.token_sink,
                "messages": ctx.messages,
            }
            return AgentResult(agent=name, response=name)

    _A.__name__ = f"Agent_{name}"
    _A.name = name
    _A.description = name
    _A.enabled = True
    _A.timeout = 30
    agent(_A)
    register_instance(name, _A())


def _state(names: list[str], **extra) -> dict:
    compound = len(names) > 1
    ctx = AgentContext(
        session_id="s1",
        prompt="p",
        memory=MemoryContext(),
        messages=[{"role": "user", "content": "p"}],
        timezone="Europe/Lisbon",
        extensions={"user_message_id": "m1"},
    )
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
        "agent_context": ctx,
        "image_data": None,
        **extra,
    }


def _lisbon_abbreviation(line: str) -> bool:
    return line.endswith(("WET", "WEST"))


async def test_single_path_child_carries_timezone_and_extensions():
    seen: dict = {}
    _register("a", seen)
    await execute_tool(_state(["a"]), {"configurable": {}})
    assert seen["a"]["timezone"] == "Europe/Lisbon"
    assert seen["a"]["message_id"] == "m1"


async def test_single_path_prompt_shows_lisbon_time():
    seen: dict = {}
    _register("a", seen)
    await execute_tool(_state(["a"]), {"configurable": {}})
    assert _lisbon_abbreviation(seen["a"]["prompt_line"])


async def test_each_compound_subtask_carries_timezone_and_extensions():
    seen: dict = {}
    _register("a", seen)
    _register("b", seen)
    await execute_tool(_state(["a", "b"]), {"configurable": {}})
    for name in ("a", "b"):
        assert seen[name]["timezone"] == "Europe/Lisbon"
        assert seen[name]["message_id"] == "m1"
        assert _lisbon_abbreviation(seen[name]["prompt_line"])


async def test_compound_subtasks_get_no_token_sink():
    seen: dict = {}
    _register("a", seen)
    _register("b", seen)

    def sink(token):
        return None

    await execute_tool(_state(["a", "b"]), {"configurable": {"token_sink": sink}})
    assert seen["a"]["token_sink"] is None
    assert seen["b"]["token_sink"] is None


async def test_single_path_gets_the_token_sink():
    seen: dict = {}
    _register("a", seen)

    def sink(token):
        return None

    await execute_tool(_state(["a"]), {"configurable": {"token_sink": sink}})
    assert seen["a"]["token_sink"] is sink


async def test_image_turn_child_gets_the_image_message():
    seen: dict = {}
    _register("a", seen)
    state = _state(["a"], image_data=b"\x89PNG", image_mime="image/png")
    await execute_tool(state, {"configurable": {}})
    content = seen["a"]["messages"][0]["content"]
    assert content[0]["type"] == "image_url"
    assert content[0]["image_url"]["url"].startswith("data:image/png;base64,")
