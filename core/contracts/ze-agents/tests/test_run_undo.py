"""`BaseAgent.run_undo` runs an undo tool outside the model loop (Phase 180)."""

from __future__ import annotations

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.registry import clear_registry
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentResult, GateDecision


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    yield
    clear_registry()
    clear_tool_registry()


class _Store:
    def __init__(self) -> None:
        self.cancelled: list[str] = []


def _agent(store: _Store) -> BaseAgent:
    class _A(BaseAgent):
        name = "reminders"
        description = "d"
        tools = []

        def tool_deps(self) -> dict:
            return {"store": store}

        async def run(self, ctx):
            return AgentResult(agent=self.name, response="ok")

    return _A()


def test_default_tool_deps_is_empty():
    class _A(BaseAgent):
        name = "a"
        description = "d"
        tools = []

        async def run(self, ctx):
            return AgentResult(agent=self.name, response="ok")

    assert _A().tool_deps() == {}


async def test_run_undo_merges_deps_with_args():
    store = _Store()

    @tool(
        access=ToolAccess.WRITE,
        description="c",
        reversibility=ToolReversibility.IRREVERSIBLE,
    )
    async def cancel_reminder(store: _Store, reminder_id: str) -> dict:
        store.cancelled.append(reminder_id)
        return {"ok": True}

    tc = await _agent(store).run_undo(
        "cancel_reminder", {"reminder_id": "r1"}, session_id="thread-1"
    )
    assert tc.success is True
    assert tc.agent == "reminders"
    assert tc.args == {"reminder_id": "r1"}
    assert store.cancelled == ["r1"]


async def test_run_undo_context_is_a_normal_executing_context():
    seen = {}

    class _Spy(BaseAgent):
        name = "spy"
        description = "d"
        tools = []

        async def run(self, ctx):
            return AgentResult(agent=self.name, response="ok")

        async def call_tool(self, name, ctx, **kwargs):
            seen["ctx"] = ctx
            return await super().call_tool(name, ctx, **kwargs)

    @tool(
        access=ToolAccess.WRITE,
        description="c",
        reversibility=ToolReversibility.IRREVERSIBLE,
    )
    async def undo_it() -> dict:
        return {"ok": True}

    await _Spy().run_undo("undo_it", {}, session_id="thread-9")
    ctx = seen["ctx"]
    assert ctx.session_id == "thread-9"
    assert ctx.gate_decision is GateDecision.EXECUTE
    assert ctx.retry_mode is False
    assert ctx.intent == "rollback"


async def test_run_undo_reports_tool_failure_without_raising():
    @tool(
        access=ToolAccess.WRITE,
        description="c",
        reversibility=ToolReversibility.IRREVERSIBLE,
    )
    async def broken() -> dict:
        raise RuntimeError("db down")

    tc = await _agent(_Store()).run_undo("broken", {}, session_id="t")
    assert tc.success is False
    assert "db down" in tc.error
