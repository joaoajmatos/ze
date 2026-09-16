from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.hooks import clear_hooks, register_hook
from ze_agents.interrupt import tool_interrupt_fn
from ze_agents.registry import clear_registry
from ze_agents.tool import ToolAccess, clear_tool_registry, get_tool, tool
from ze_agents.types import AgentContext, AgentResult
from ze_memory.constraint_veto import (
    ConstraintVetoHook,
    ConstraintWriteView,
    ReviewedConstraint,
    VetoDecision,
    match_constraints,
)


@pytest.fixture(autouse=True)
def _clean():
    clear_registry()
    clear_tool_registry()
    clear_hooks()
    yield
    clear_registry()
    clear_tool_registry()
    clear_hooks()


def _ctx() -> AgentContext:
    return AgentContext(session_id="s1", prompt="go", intent="create")


def _agent() -> BaseAgent:
    class _A(BaseAgent):
        name = "test"
        description = "test"
        tools = []

        async def run(self, ctx: AgentContext) -> AgentResult:
            return AgentResult(agent=self.name, response="ok")

    return _A()


def _fact(value: str) -> ReviewedConstraint:
    return ReviewedConstraint(id=uuid4(), value=value)


def test_reviewed_filter_query_requires_reviewed_and_not_contradicted():
    from ze_memory.constraint_veto import load_reviewed_constraints
    import inspect

    source = inspect.getsource(load_reviewed_constraints)
    assert "reviewed = true" in source
    assert "contradicted = false" in source
    assert "predicate = 'constraint'" in source


async def test_marked_dummy_tool_is_blocked_without_running_body():
    ran = []

    @tool(
        access=ToolAccess.WRITE,
        description="not mail",
        constraint_gate=True,
        constraint_describe=lambda args: ConstraintWriteView(
            tool_name="ping_pager",
            kind="outbound_message",
            channel="email",
            parties=[args.get("to", "")],
            when=datetime(2026, 9, 16, 23, 0, tzinfo=ZoneInfo("UTC")),
            summary="ping",
        ),
    )
    async def ping_pager(to: str) -> str:
        ran.append(to)
        return "sent"

    register_hook(
        ConstraintVetoHook(
            constraints=[_fact("never email after 22:00")],
            user_timezone="UTC",
        )
    )
    tc = await _agent().call_tool("ping_pager", _ctx(), to="bob@example.com")
    assert ran == []
    assert tc.success is False
    assert tc.result["ok"] is False
    assert tc.result["veto"] is True
    assert tc.result["constraint_ids"]
    assert "error" in tc.result


async def test_unmarked_dummy_tool_completes():
    ran = []

    @tool(access=ToolAccess.WRITE, description="ungated twin")
    async def ping_pager_free(to: str) -> str:
        ran.append(to)
        return "sent"

    register_hook(
        ConstraintVetoHook(
            constraints=[_fact("never email after 22:00")],
            user_timezone="UTC",
        )
    )
    tc = await _agent().call_tool("ping_pager_free", _ctx(), to="bob@example.com")
    assert ran == ["bob@example.com"]
    assert tc.success is True
    payload = tc.result
    if isinstance(payload, dict):
        assert payload.get("veto") is not True


async def test_unmarked_remember_fact_is_not_intercepted():
    ran = []

    @tool(access=ToolAccess.WRITE, description="remember")
    async def remember_fact(value: str) -> dict:
        ran.append(value)
        return {"ok": True, "id": "x"}

    register_hook(
        ConstraintVetoHook(
            constraints=[_fact("never email after 22:00")],
            user_timezone="UTC",
        )
    )
    tc = await _agent().call_tool("remember_fact", _ctx(), value="likes tea")
    assert ran == ["likes tea"]
    assert tc.success is True
    assert get_tool("remember_fact").constraint_gate is False


def test_email_only_constraint_does_not_auto_hit_calendar():
    view = ConstraintWriteView(
        tool_name="create_event",
        kind="calendar_mutation",
        channel="calendar",
        parties=[],
        when=datetime(2026, 9, 16, 23, 0, tzinfo=ZoneInfo("UTC")),
        summary="dentist",
    )
    decision, ids, _ = match_constraints(
        view,
        [_fact("never email after 22:00")],
        user_timezone="UTC",
    )
    assert decision is VetoDecision.ALLOW
    assert ids == []


def test_named_party_and_matching_channel_refuses():
    view = ConstraintWriteView(
        tool_name="send_email",
        kind="outbound_message",
        channel="email",
        parties=["Bob"],
        when=datetime(2026, 9, 16, 10, 0, tzinfo=ZoneInfo("UTC")),
        summary="hi bob",
    )
    decision, ids, error = match_constraints(
        view,
        [_fact("never email Bob")],
        user_timezone="UTC",
    )
    assert decision is VetoDecision.REFUSE
    assert ids
    assert "Bob" in error or "constraint" in error.lower()


def test_ambiguous_constraint_confirms():
    view = ConstraintWriteView(
        tool_name="send_email",
        kind="outbound_message",
        channel="email",
        parties=["Ada"],
        when=datetime(2026, 9, 16, 10, 0, tzinfo=ZoneInfo("UTC")),
        summary="hello",
    )
    decision, ids, _ = match_constraints(
        view,
        [_fact("be careful with messages")],
        user_timezone="UTC",
    )
    assert decision is VetoDecision.CONFIRM
    assert ids


def test_unreviewed_shape_is_not_in_hook_input():
    view = ConstraintWriteView(
        tool_name="ping_pager",
        kind="outbound_message",
        channel="email",
        parties=["Ada"],
        summary="x",
    )
    decision, _, _ = match_constraints(view, [], user_timezone="UTC")
    assert decision is VetoDecision.ALLOW


async def test_ambiguous_confirm_executes_after_approve():
    ran = []

    @tool(
        access=ToolAccess.WRITE,
        description="gated",
        constraint_gate=True,
        constraint_describe=lambda args: ConstraintWriteView(
            tool_name="note_contact",
            kind="outbound_message",
            channel="email",
            parties=["Ada"],
            summary="note",
        ),
    )
    async def note_contact(to: str) -> str:
        ran.append(to)
        return "ok"

    register_hook(
        ConstraintVetoHook(
            constraints=[_fact("be careful with messages")],
            user_timezone="UTC",
        )
    )
    token = tool_interrupt_fn.set(lambda payload: {"choice": "approve"})
    try:
        tc = await _agent().call_tool("note_contact", _ctx(), to="Ada")
    finally:
        tool_interrupt_fn.reset(token)
    assert ran == ["Ada"]
    assert tc.success is True


async def test_ambiguous_confirm_without_interrupt_refuses():
    ran = []

    @tool(
        access=ToolAccess.WRITE,
        description="gated",
        constraint_gate=True,
        constraint_describe=lambda args: ConstraintWriteView(
            tool_name="note_contact",
            kind="outbound_message",
            channel="email",
            parties=["Ada"],
            summary="note",
        ),
    )
    async def note_contact(to: str) -> str:
        ran.append(to)
        return "ok"

    register_hook(
        ConstraintVetoHook(
            constraints=[_fact("be careful with messages")],
            user_timezone="UTC",
        )
    )
    tc = await _agent().call_tool("note_contact", _ctx(), to="Ada")
    assert ran == []
    assert tc.result["veto"] is True


async def test_load_reviewed_constraints_skips_unreviewed_and_contradicted():
    from ze_memory.constraint_veto import load_reviewed_constraints

    kept_id = uuid4()

    class _Conn:
        async def fetch(self, sql, *args):
            assert "reviewed = true" in sql
            assert "contradicted = false" in sql
            return [{"id": kept_id, "value": "never email after 22:00"}]

    class _CM:
        async def __aenter__(self):
            return _Conn()

        async def __aexit__(self, *args):
            return None

    store = MagicMock()
    store.pool = MagicMock()
    store.pool.acquire = MagicMock(return_value=_CM())
    facts = await load_reviewed_constraints(store)
    assert len(facts) == 1
    assert facts[0].id == kept_id
