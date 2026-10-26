"""Retry runs: irreversible writes refused, reversible writes run under normal gates,
admission skipped (Phase 165 US3/SC-004, Phase 180 one retry policy)."""

from __future__ import annotations

from ze_agents.types import WriteGateState
import asyncio
from unittest.mock import AsyncMock

import pytest

from ze_agents.base_agent import RETRY_WRITE_REFUSAL, BaseAgent
from ze_agents.registry import clear_registry
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext, AgentResult
from ze_core.orchestration.nodes import memory
from ze_memory.retriever import PostgresMemoryStore as MemoryStore
from ze_memory.types import MemoryContext
from tests.orchestration.test_nodes import base_state, make_config


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    yield
    clear_registry()
    clear_tool_registry()


def _agent() -> BaseAgent:
    class _A(BaseAgent):
        name = "test"
        description = "d"
        tools = []

        async def run(self, ctx):
            return AgentResult(agent=self.name, response="ok")

    return _A()


def _ctx(retry: bool) -> AgentContext:
    return AgentContext(session_id="s1", prompt="hi", write_gate=WriteGateState(retry_mode=retry))


async def test_write_tool_refused_in_retry_mode_and_body_never_runs():
    ran = []

    @tool(
        access=ToolAccess.WRITE,
        description="w",
        reversibility=ToolReversibility.IRREVERSIBLE,
    )
    async def send_thing(x: str) -> str:
        ran.append(x)
        return "sent"

    tc = await _agent().call_tool("send_thing", _ctx(True), x="a")
    assert ran == []
    assert tc.success is False
    assert tc.result == RETRY_WRITE_REFUSAL
    assert "retry" in tc.error


async def test_read_tool_still_runs_in_retry_mode():
    @tool(access=ToolAccess.READ, description="r")
    async def look(x: str) -> str:
        return f"saw {x}"

    tc = await _agent().call_tool("look", _ctx(True), x="a")
    assert tc.success is True
    assert tc.result == "saw a"


async def test_write_tool_runs_normally_outside_retry_mode():
    ran = []

    @tool(
        access=ToolAccess.WRITE,
        description="w",
        reversibility=ToolReversibility.IRREVERSIBLE,
        asks_first=False,
        no_ask_reason="test tool, not under confirmation",
    )
    async def send_thing(x: str) -> str:
        ran.append(x)
        return "sent"

    tc = await _agent().call_tool("send_thing", _ctx(False), x="a")
    assert ran == ["a"]
    assert tc.success is True


async def test_delegate_subcontext_inherits_retry_mode():
    from ze_agents.delegate import DELEGATE_TOOL_NAME, run_delegate
    from ze_agents.registry import register_instance

    seen = []

    class _Spec(BaseAgent):
        name = "calendar"
        description = "d"
        tools = []

        async def run(self, ctx):
            seen.append(ctx.write_gate.retry_mode)
            return AgentResult(agent=self.name, response="done")

    register_instance("calendar", _Spec())
    ctx = _ctx(True)
    call = await run_delegate(
        {"agent_name": "calendar", "objective": "check tuesday"},
        ctx,
        0,
        caller_name="companion",
    )
    assert call.tool_name == DELEGATE_TOOL_NAME
    assert seen == [True]


async def test_write_memory_in_retry_skips_admission_but_extends_history():
    store = AsyncMock(spec=MemoryStore)
    fact_extractor = AsyncMock()
    turn_extractor = AsyncMock()
    hook = AsyncMock()
    cfg = make_config(memory_store=store)
    cfg["configurable"].update(
        retry_mode=True,
        fact_extractor=fact_extractor,
        turn_extractor=turn_extractor,
        memory_hooks=[hook],
    )
    ctx = AgentContext(session_id="s1", prompt="hi", memory=MemoryContext())
    state = base_state(
        agent_context=ctx,
        agent_result=AgentResult(agent="research", response="new reply"),
        messages=[{"role": "user", "content": "earlier"}],
    )
    result = await memory.write_memory(state, cfg)
    await asyncio.sleep(0)

    store.write_episode.assert_not_called()
    store.propose_events.assert_not_called()
    store.upsert_entity.assert_not_called()
    fact_extractor.assert_not_called()
    turn_extractor.assert_not_called()
    hook.assert_not_called()
    assert result["messages"][-2:] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "new reply"},
    ]


async def test_write_memory_without_retry_still_writes_episode():
    store = AsyncMock(spec=MemoryStore)
    cfg = make_config(memory_store=store)
    ctx = AgentContext(session_id="s1", prompt="hi", memory=MemoryContext())
    await memory.write_memory(
        base_state(
            agent_context=ctx, agent_result=AgentResult(agent="research", response="r")
        ),
        cfg,
    )
    await asyncio.sleep(0)
    store.write_episode.assert_called_once()


async def test_write_memory_makes_one_extractor_call_and_stores_its_events_and_entities():
    from ze_memory.extractor import TurnProposals
    from ze_memory.types import Entity, Event

    store = AsyncMock(spec=MemoryStore)
    event = Event(
        id=None, event_type="meal", title="Dinner", start_at=None, end_at=None
    )
    entity = Entity(
        id=None, entity_type="person", canonical_name="Ana", aliases=[], attrs={}
    )
    turn_extractor = AsyncMock(
        return_value=TurnProposals(events=[event], entities=[entity])
    )
    cfg = make_config(memory_store=store)
    cfg["configurable"]["turn_extractor"] = turn_extractor
    ctx = AgentContext(
        session_id="s1", prompt="dinner with Ana", memory=MemoryContext()
    )
    await memory.write_memory(
        base_state(
            agent_context=ctx, agent_result=AgentResult(agent="research", response="r")
        ),
        cfg,
    )
    await asyncio.sleep(0)

    turn_extractor.assert_awaited_once()
    store.propose_events.assert_called_once_with([event])
    store.upsert_entity.assert_called_once_with(entity)


async def test_write_memory_labels_its_llm_calls_as_memory_write():
    from ze_core.telemetry.context import get_cost_context

    seen = []

    async def _extractor(configurable, *, prompt, response):
        from ze_memory.extractor import TurnProposals

        seen.append(get_cost_context().agent)
        return TurnProposals()

    store = AsyncMock(spec=MemoryStore)
    cfg = make_config(memory_store=store)
    cfg["configurable"]["turn_extractor"] = _extractor
    ctx = AgentContext(session_id="s1", prompt="hello there", memory=MemoryContext())
    await memory.write_memory(
        base_state(
            agent_context=ctx, agent_result=AgentResult(agent="research", response="r")
        ),
        cfg,
    )
    assert seen == ["memory_write"]


async def test_write_memory_survives_a_turn_extractor_that_raises():
    store = AsyncMock(spec=MemoryStore)
    hook = AsyncMock()
    cfg = make_config(memory_store=store)
    cfg["configurable"]["turn_extractor"] = AsyncMock(side_effect=TypeError("boom"))
    cfg["configurable"]["memory_hooks"] = [hook]
    ctx = AgentContext(
        session_id="s1", prompt="dinner with Ana", memory=MemoryContext()
    )
    result = await memory.write_memory(
        base_state(
            agent_context=ctx, agent_result=AgentResult(agent="research", response="r")
        ),
        cfg,
    )
    await asyncio.sleep(0)

    assert result["messages"][-1] == {"role": "assistant", "content": "r"}
    hook.assert_called_once()
    store.propose_events.assert_not_called()


async def test_write_memory_with_null_participants_in_the_model_reply():
    """The real extractor on a reply with null list fields: the turn still completes."""
    from ze_memory.extractor import gather_turn_proposals

    store = AsyncMock(spec=MemoryStore)
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value=(
            '{"events":[{"title":"x","event_type":"meeting","participants":null}],'
            '"entities":[{"name":"Ana","entity_type":"person","aliases":null}]}'
        )
    )
    cfg = make_config(memory_store=store)
    cfg["configurable"]["turn_extractor"] = gather_turn_proposals
    cfg["configurable"]["openrouter_client"] = client
    ctx = AgentContext(session_id="s1", prompt="met Ana today", memory=MemoryContext())
    result = await memory.write_memory(
        base_state(
            agent_context=ctx, agent_result=AgentResult(agent="research", response="r")
        ),
        cfg,
    )
    await asyncio.sleep(0)
    assert result["messages"][-1]["content"] == "r"
