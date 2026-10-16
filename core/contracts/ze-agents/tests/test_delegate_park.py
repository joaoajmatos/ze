"""A specialist's park propagates through delegate_to_agent (Phase 181, D2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.delegate import DELEGATE_TOOL_NAME, run_delegate
from ze_agents.errors import LoopParked
from ze_agents.registry import agent, clear_registry, register_instance
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext, AgentResult, GateDecision

calls: list[tuple[str, dict]] = []


async def _eval_execute(_agent: str, _intent: str) -> GateDecision:
    return GateDecision.EXECUTE


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    calls.clear()

    async def list_events() -> str:
        calls.append(("list_events", {}))
        return "events"

    tool(access=ToolAccess.READ, description="list")(list_events)

    async def delete_event(event_id: str = "") -> str:
        calls.append(("delete_event", {"event_id": event_id}))
        return "deleted"

    tool(
        access=ToolAccess.WRITE,
        description="delete",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="deleted a calendar event",
    )(delete_event)
    yield
    clear_registry()
    clear_tool_registry()


def _script(*responses):
    client = MagicMock()
    client.complete_with_tools = AsyncMock(side_effect=list(responses))
    client.complete = AsyncMock(return_value="fallback")
    return client


def _ctx() -> AgentContext:
    return AgentContext(
        session_id="s",
        prompt="p",
        intent="reason",
        evaluate_delegate=_eval_execute,
    )


def _register_calendar(client) -> BaseAgent:
    async def _run(self, ctx: AgentContext) -> AgentResult:
        text, tcs = await self.agentic_loop(
            ctx,
            client,
            list(ctx.messages),
            system="s",
            tool_names=["list_events", "delete_event"],
        )
        return AgentResult(agent=self.name, response=text, tool_calls=tcs)

    cls = type(
        "_Calendar",
        (BaseAgent,),
        {"name": "calendar", "description": "cal", "tools": [], "run": _run},
    )
    agent(cls)
    inst = cls()
    register_instance("calendar", inst)
    return inst


async def test_run_delegate_returns_child_loop_when_specialist_parks() -> None:
    _register_calendar(
        _script(
            (
                None,
                [{"id": "k1", "name": "delete_event", "arguments": {"event_id": "e1"}}],
            )
        )
    )
    tc = await run_delegate(
        {"agent_name": "calendar", "objective": "delete my 3pm"},
        _ctx(),
        0,
        caller_name="companion",
    )
    assert tc.tool_name == DELEGATE_TOOL_NAME
    assert tc.parked is None
    assert tc.gate == "parked" and tc.success is False
    assert tc.child_loop is not None
    assert tc.child_loop.agent == "calendar"
    assert tc.child_loop.parked[0].args == {"event_id": "e1"}
    assert calls == []


async def test_conductor_loop_parks_behind_the_specialist() -> None:
    _register_calendar(
        _script(
            (
                None,
                [{"id": "k1", "name": "delete_event", "arguments": {"event_id": "e1"}}],
            )
        )
    )

    class _Companion(BaseAgent):
        name = "companion"
        description = "c"
        tools = ["list_events"]

        async def run(self, ctx):  # pragma: no cover
            raise NotImplementedError

    companion_client = _script(
        (
            None,
            [
                {"id": "d1", "name": "list_events", "arguments": {}},
                {
                    "id": "d2",
                    "name": DELEGATE_TOOL_NAME,
                    "arguments": {
                        "agent_name": "calendar",
                        "objective": "delete my 3pm",
                    },
                },
            ],
        )
    )
    with pytest.raises(LoopParked) as info:
        await _Companion().agentic_loop(
            _ctx(), companion_client, [{"role": "user", "content": "x"}], system="s"
        )
    loop = info.value.loop
    assert loop.agent == "companion"
    assert loop.child is not None and loop.child.agent == "calendar"
    assert loop.child_call_id == "d2"
    assert loop.child_arguments["agent_name"] == "calendar"
    assert [a.tool_name for a in loop.accumulated] == ["list_events"]
    assert calls == [("list_events", {})]
    assert [w.tool for w in loop.all_parked()] == ["delete_event"]


async def test_second_delegate_in_the_same_response_is_deferred() -> None:
    _register_calendar(
        _script(
            (
                None,
                [{"id": "k1", "name": "delete_event", "arguments": {"event_id": "e1"}}],
            )
        )
    )

    class _Companion(BaseAgent):
        name = "companion"
        description = "c"
        tools = []

        async def run(self, ctx):  # pragma: no cover
            raise NotImplementedError

    d = {"agent_name": "calendar", "objective": "o"}
    client = _script(
        (
            None,
            [
                {"id": "d1", "name": DELEGATE_TOOL_NAME, "arguments": d},
                {"id": "d2", "name": DELEGATE_TOOL_NAME, "arguments": d},
            ],
        )
    )
    with pytest.raises(LoopParked) as info:
        await _Companion().agentic_loop(_ctx(), client, [], system="s")
    loop = info.value.loop
    assert loop.child_call_id == "d1"
    tool_msgs = [m for m in loop.messages if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["d2"]
    assert "waiting for the user's approval" in tool_msgs[0]["content"]
