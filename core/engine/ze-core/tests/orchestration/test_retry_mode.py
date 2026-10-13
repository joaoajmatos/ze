"""Retry runs: irreversible writes refused, reversible writes run under normal gates,
admission skipped (Phase 165 US3/SC-004, Phase 180 one retry policy)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from ze_agents.base_agent import RETRY_WRITE_REFUSAL, BaseAgent
from ze_agents.registry import clear_registry
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext, AgentResult, GateDecision
from ze_core.capability.gate import CapabilityGate
from ze_core.orchestration.nodes import execution, memory
from ze_memory.retriever import PostgresMemoryStore as MemoryStore
from ze_memory.types import MemoryContext
from tests.orchestration.test_nodes import base_state, make_config, make_envelope


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
    return AgentContext(session_id="s1", prompt="hi", intent="read", retry_mode=retry)


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
            seen.append(ctx.retry_mode)
            return AgentResult(agent=self.name, response="done")

    register_instance("calendar", _Spec())
    ctx = _ctx(True)
    ctx.evaluate_delegate = lambda agent, intent: GateDecision.EXECUTE
    call = await run_delegate(
        {"agent_name": "calendar", "objective": "check tuesday"},
        ctx,
        0,
        caller_name="companion",
    )
    assert call.tool_name == DELEGATE_TOOL_NAME
    assert seen == [True]


async def test_capability_check_keeps_confirmation_gate_in_retry():
    gate = AsyncMock(spec=CapabilityGate)
    gate.evaluate = lambda **kw: GateDecision.AWAIT_CONFIRMATION
    cfg = make_config(capability_gate=gate)
    cfg["configurable"]["retry_mode"] = True
    result = await execution.capability_check(
        base_state(envelope=make_envelope(intent="write")), cfg
    )
    assert result["gate_decision"] is GateDecision.AWAIT_CONFIRMATION


async def test_capability_check_keeps_draft_gate_in_retry():
    gate = AsyncMock(spec=CapabilityGate)
    gate.evaluate = lambda **kw: GateDecision.DRAFT
    cfg = make_config(capability_gate=gate)
    cfg["configurable"]["retry_mode"] = True
    result = await execution.capability_check(
        base_state(envelope=make_envelope(intent="write")), cfg
    )
    assert result["gate_decision"] is GateDecision.DRAFT


async def test_capability_check_blocked_stays_blocked_in_retry():
    gate = AsyncMock(spec=CapabilityGate)
    gate.evaluate = lambda **kw: GateDecision.BLOCKED
    cfg = make_config(capability_gate=gate)
    cfg["configurable"]["retry_mode"] = True
    result = await execution.capability_check(base_state(), cfg)
    assert result["gate_decision"] is GateDecision.BLOCKED


async def test_capability_check_unchanged_without_retry():
    gate = AsyncMock(spec=CapabilityGate)
    gate.evaluate = lambda **kw: GateDecision.AWAIT_CONFIRMATION
    result = await execution.capability_check(
        base_state(), make_config(capability_gate=gate)
    )
    assert result["gate_decision"] is GateDecision.AWAIT_CONFIRMATION


async def test_write_memory_in_retry_skips_admission_but_extends_history():
    store = AsyncMock(spec=MemoryStore)
    fact_extractor = AsyncMock()
    event_extractor = AsyncMock()
    entity_extractor = AsyncMock()
    hook = AsyncMock()
    cfg = make_config(memory_store=store)
    cfg["configurable"].update(
        retry_mode=True,
        fact_extractor=fact_extractor,
        event_extractor=event_extractor,
        entity_extractor=entity_extractor,
        memory_hooks=[hook],
    )
    ctx = AgentContext(
        session_id="s1", prompt="hi", intent="read", memory=MemoryContext()
    )
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
    event_extractor.assert_not_called()
    entity_extractor.assert_not_called()
    hook.assert_not_called()
    assert result["messages"][-2:] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "new reply"},
    ]


async def test_write_memory_without_retry_still_writes_episode():
    store = AsyncMock(spec=MemoryStore)
    cfg = make_config(memory_store=store)
    ctx = AgentContext(
        session_id="s1", prompt="hi", intent="read", memory=MemoryContext()
    )
    await memory.write_memory(
        base_state(
            agent_context=ctx, agent_result=AgentResult(agent="research", response="r")
        ),
        cfg,
    )
    await asyncio.sleep(0)
    store.write_episode.assert_called_once()


async def test_compound_capability_check_keeps_confirmations_in_retry():
    from ze_core.routing.types import SubTask

    gate = AsyncMock(spec=CapabilityGate)
    gate.evaluate = lambda **kw: GateDecision.AWAIT_CONFIRMATION
    env = make_envelope(
        is_compound=True,
        subtasks=[
            SubTask(agent="a", intent="write", prompt="x"),
            SubTask(agent="b", intent="write", prompt="y"),
        ],
    )
    cfg = make_config(capability_gate=gate)
    cfg["configurable"]["retry_mode"] = True
    result = await execution.capability_check(base_state(envelope=env), cfg)
    assert [d["decision"] for d in result["subtask_gate_decisions"]] == [
        GateDecision.AWAIT_CONFIRMATION,
        GateDecision.AWAIT_CONFIRMATION,
    ]


async def test_delegate_confirmation_is_kept_in_retry():
    from ze_agents.delegate import run_delegate
    from ze_agents.interrupt import tool_interrupt_fn
    from ze_agents.registry import register_instance

    seen = []
    prompts = []

    class _Spec(BaseAgent):
        name = "messenger"
        description = "d"
        tools = []

        async def run(self, ctx):
            seen.append(ctx.gate_decision)
            return AgentResult(agent=self.name, response="done")

    register_instance("messenger", _Spec())
    ctx = _ctx(True)
    ctx.evaluate_delegate = lambda agent, intent: GateDecision.AWAIT_CONFIRMATION

    def _approve(payload):
        prompts.append(payload["kind"])
        return {"choice": "approve"}

    token = tool_interrupt_fn.set(_approve)
    try:
        call = await run_delegate(
            {"agent_name": "messenger", "objective": "mail ana"},
            ctx,
            0,
            caller_name="companion",
        )
    finally:
        tool_interrupt_fn.reset(token)
    assert prompts == ["delegate"]
    assert call.success is True
    assert seen == [GateDecision.EXECUTE]
