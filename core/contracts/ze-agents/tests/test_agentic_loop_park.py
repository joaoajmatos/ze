"""`agentic_loop` parks asks-first calls and raises LoopParked (Phase 181, D2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.errors import LoopParked
from ze_agents.registry import clear_registry
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext, AgentResult

calls: list[tuple[str, dict]] = []


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    calls.clear()

    async def list_events() -> str:
        calls.append(("list_events", {}))
        return "3pm dentist"

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

    async def send_email(to: str = "") -> str:
        calls.append(("send_email", {"to": to}))
        return "sent"

    tool(
        access=ToolAccess.WRITE,
        description="send",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="sent an email",
    )(send_email)
    yield
    clear_registry()
    clear_tool_registry()


class _Agent(BaseAgent):
    name = "calendar"
    description = "test"
    tools = ["list_events", "delete_event", "send_email"]

    async def run(self, ctx: AgentContext) -> AgentResult:
        return AgentResult(agent=self.name, response="ok")


def _ctx() -> AgentContext:
    return AgentContext(
        session_id="s",
        prompt="p",
    )


def _client(*responses):
    client = MagicMock()
    client.complete_with_tools = AsyncMock(side_effect=list(responses))
    client.complete = AsyncMock(return_value="fallback")
    return client


def _tc(id_: str, name: str, **args):
    return {"id": id_, "name": name, "arguments": args}


async def test_read_runs_write_parks() -> None:
    ctx = _ctx()
    client = _client(
        (None, [_tc("c1", "list_events"), _tc("c2", "delete_event", event_id="e1")])
    )
    with pytest.raises(LoopParked) as info:
        await _Agent().agentic_loop(
            ctx, client, [{"role": "user", "content": "delete my 3pm"}], system="s"
        )
    loop = info.value.loop
    assert calls == [("list_events", {})]
    assert loop.agent == "calendar"
    assert loop.iteration == 0
    assert [a.tool_name for a in loop.accumulated] == ["list_events"]
    assert [(p.call_id, p.tool, p.args) for p in loop.parked] == [
        ("c2", "delete_event", {"event_id": "e1"})
    ]
    roles = [m["role"] for m in loop.messages]
    assert roles == ["user", "assistant", "tool"]
    assert loop.messages[-1]["tool_call_id"] == "c1"
    assert ctx.loop_active is False


async def test_two_parked_calls_keep_model_order() -> None:
    client = _client(
        (
            None,
            [_tc("c1", "delete_event", event_id="a"), _tc("c2", "send_email", to="x")],
        )
    )
    with pytest.raises(LoopParked) as info:
        await _Agent().agentic_loop(_ctx(), client, [], system="s")
    assert [p.tool for p in info.value.loop.parked] == ["delete_event", "send_email"]
    assert calls == []


async def test_loop_active_inside_the_loop() -> None:
    ctx = _ctx()
    seen: list[bool] = []

    async def _complete(**kw):
        seen.append(ctx.loop_active)
        return ("done", None)

    client = MagicMock()
    client.complete_with_tools = AsyncMock(side_effect=_complete)
    await _Agent().agentic_loop(ctx, client, [], system="s")
    assert seen == [True]
    assert ctx.loop_active is False


async def test_iteration_recorded_after_earlier_iterations() -> None:
    client = _client(
        (None, [_tc("c1", "list_events")]),
        (None, [_tc("c2", "delete_event", event_id="e1")]),
    )
    with pytest.raises(LoopParked) as info:
        await _Agent().agentic_loop(_ctx(), client, [], system="s")
    assert info.value.loop.iteration == 1
    assert [a.tool_name for a in info.value.loop.accumulated] == ["list_events"]
