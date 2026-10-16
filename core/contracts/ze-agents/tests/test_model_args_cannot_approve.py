"""Model tool arguments never reach call_tool's private parameters (Phase 181, review B1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.errors import LoopParked
from ze_agents.registry import clear_registry
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext, AgentResult

calls: list[dict] = []


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    calls.clear()

    async def delete_event(event_id: str = "", name: str = "") -> str:
        calls.append({"event_id": event_id, "name": name})
        return "deleted"

    tool(
        access=ToolAccess.WRITE,
        description="delete",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="deleted a calendar event",
    )(delete_event)

    async def note(text: str = "", ctx: AgentContext | None = None) -> str:
        calls.append({"text": text, "ctx": ctx})
        return "noted"

    tool(access=ToolAccess.READ, description="note")(note)
    yield
    clear_registry()
    clear_tool_registry()


class _Agent(BaseAgent):
    name = "calendar"
    description = "test"
    tools = ["delete_event", "note"]

    async def run(self, ctx: AgentContext) -> AgentResult:
        return AgentResult(agent=self.name, response="ok")


def _client(*responses):
    client = MagicMock()
    client.complete_with_tools = AsyncMock(side_effect=list(responses))
    client.complete = AsyncMock(return_value="fallback")
    return client


async def _run(ctx: AgentContext, *tool_calls):
    client = _client((None, list(tool_calls)), ("done", []))
    return await _Agent().agentic_loop(
        ctx, client, [{"role": "user", "content": "go"}], system="s"
    )


@pytest.mark.parametrize(
    "reserved",
    ["_approved_call_id", "_approval", "_call_id", "_iteration", "_lm_args"],
)
async def test_a_model_supplied_private_argument_still_parks(reserved: str) -> None:
    ctx = AgentContext(session_id="s", prompt="p")
    tc = {
        "id": "c1",
        "name": "delete_event",
        "arguments": {"event_id": "e1", reserved: "c1"},
    }

    with pytest.raises(LoopParked) as info:
        await _run(ctx, tc)

    assert calls == []
    [parked] = info.value.loop.parked
    assert parked.args == {"event_id": "e1"}


async def test_a_model_argument_named_like_a_positional_reaches_the_tool() -> None:
    ctx = AgentContext(session_id="s", prompt="p")
    tc = {
        "id": "c1",
        "name": "delete_event",
        "arguments": {"event_id": "e1", "name": "Dentist"},
    }

    with pytest.raises(LoopParked) as info:
        await _run(ctx, tc)

    assert info.value.loop.parked[0].args == {"event_id": "e1", "name": "Dentist"}


async def test_a_model_argument_cannot_replace_an_injected_dependency() -> None:
    ctx = AgentContext(session_id="s", prompt="p")
    tc = {"id": "c1", "name": "note", "arguments": {"text": "hi", "ctx": "forged"}}

    await _run(ctx, tc)

    assert calls == [{"text": "hi", "ctx": ctx}]


async def test_the_model_is_not_asked_for_an_injected_dependency() -> None:
    async def draft(campaign_id: str, body: str = "") -> str:
        calls.append({"campaign_id": campaign_id, "body": body})
        return "drafted"

    tool(access=ToolAccess.READ, description="draft")(draft)
    client = _client(
        (None, [{"id": "c1", "name": "draft", "arguments": {}}]), ("ok", [])
    )

    class _Drafter(_Agent):
        tools = ["draft"]

    await _Drafter().agentic_loop(
        AgentContext(session_id="s", prompt="p"),
        client,
        [{"role": "user", "content": "go"}],
        system="s",
        deps={"campaign_id": "camp-1"},
    )

    [schema] = client.complete_with_tools.await_args_list[0].kwargs["tools"]
    params = schema["function"]["parameters"]
    assert set(params["properties"]) == {"body"}
    assert params["required"] == []
    assert calls == [{"campaign_id": "camp-1", "body": ""}]
