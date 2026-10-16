"""The rollback executor runs undos in order and records the truth (Phase 180 T012)."""

from __future__ import annotations

import copy
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.registry import clear_registry, register_instance
from ze_agents.reversibility import ToolReversibility
from ze_agents.rollback import current_rollback_scope
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentResult
from ze_core.conversation.retry import UndoPlanEntry
from ze_core.conversation.rollback import run_rollback


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    yield
    clear_registry()
    clear_tool_registry()


class _Agent(BaseAgent):
    description = "d"
    tools: list[str] = []

    def __init__(self, name: str, deps: dict | None = None) -> None:
        self.name = name
        self._deps = deps or {}

    def tool_deps(self) -> dict:
        return self._deps

    async def run(self, ctx):
        return AgentResult(agent=self.name, response="ok")


def _step(call_index: int, undo_tool="undo_a", agent="owner", **args) -> UndoPlanEntry:
    return UndoPlanEntry(
        entry_id=f"e{call_index}",
        call_index=call_index,
        tool=f"make_{call_index}",
        undo_tool=undo_tool,
        agent=agent,
        effect_phrase=f"did {call_index}",
        undo_note="",
        undo_args=args or {"id": str(call_index)},
    )


def _store():
    store = AsyncMock()
    store.snapshots = []

    async def _set(mid, record):
        store.snapshots.append((mid, copy.deepcopy(record)))

    store.set_rollback.side_effect = _set
    return store


def _undo(name: str, log: list, result=None, raises=None):
    async def _impl(id: str) -> dict:
        log.append((name, id, current_rollback_scope()))
        if raises:
            raise raises
        return result if result is not None else {"ok": True}

    _impl.__name__ = name
    tool(
        access=ToolAccess.WRITE,
        description=name,
        reversibility=ToolReversibility.IRREVERSIBLE,
    )(_impl)


async def _run(plan, store, mid=None):
    return await run_rollback(
        plan,
        message_id=mid or uuid4(),
        thread_id="t1",
        session_id="t1",
        message_store=store,
    )


async def test_runs_in_plan_order_and_records_every_step():
    calls: list = []
    _undo("undo_a", calls)
    register_instance("owner", _Agent("owner"))
    store, mid = _store(), uuid4()
    record = await _run([_step(2), _step(1), _step(0)], store, mid)
    assert [c[1] for c in calls] == ["2", "1", "0"]
    assert [e.outcome for e in record.entries] == ["undone"] * 3
    assert record.state == "rolled_back_retry_failed"
    assert [len(r.entries) for _, r in store.snapshots] == [3, 3, 3]
    assert [[e.outcome for e in r.entries] for _, r in store.snapshots] == [
        ["undone", "not_attempted", "not_attempted"],
        ["undone", "undone", "not_attempted"],
        ["undone", "undone", "undone"],
    ]
    assert all(m == mid for m, _ in store.snapshots)
    assert store.snapshots[0][1].state == "partial"


async def test_failure_stops_and_marks_rest_not_attempted():
    calls: list = []
    _undo("undo_a", calls)
    _undo("undo_b", calls, result={"error": "reminder already fired"})
    register_instance("owner", _Agent("owner"))
    store = _store()
    record = await _run([_step(2), _step(1, undo_tool="undo_b"), _step(0)], store)
    assert [c[0] for c in calls] == ["undo_a", "undo_b"]
    assert [e.outcome for e in record.entries] == ["undone", "failed", "not_attempted"]
    assert record.state == "partial"
    assert record.entries[1].failure_code == "reminder already fired"
    assert record.entries[1].at is not None
    assert record.entries[2].at is None
    assert store.snapshots[-1][1] == record


@pytest.mark.parametrize("result", [{"error": "x"}, {"ok": False}, {"status": "error"}])
async def test_error_dict_result_counts_as_failure(result):
    _undo("undo_a", [], result=result)
    register_instance("owner", _Agent("owner"))
    record = await _run([_step(0)], _store())
    assert record.entries[0].outcome == "failed"
    assert record.state == "partial"


async def test_failure_code_is_truncated():
    _undo("undo_a", [], result={"error": "x" * 500})
    register_instance("owner", _Agent("owner"))
    record = await _run([_step(0)], _store())
    assert len(record.entries[0].failure_code) == 120


async def test_missing_agent_fails_without_raising():
    store = _store()
    record = await _run([_step(0, agent="ghost")], store)
    assert record.entries[0].outcome == "failed"
    assert record.entries[0].failure_code == "UnknownAgentError"
    store.set_rollback.assert_awaited_once()


async def test_missing_undo_tool_fails():
    register_instance("owner", _Agent("owner"))
    record = await _run([_step(0, undo_tool="nope")], _store())
    assert record.entries[0].outcome == "failed"
    assert record.entries[0].failure_code


async def test_exception_in_undo_is_a_failed_entry():
    _undo("undo_a", [], raises=RuntimeError("db down"))
    register_instance("owner", _Agent("owner"))
    record = await _run([_step(1), _step(0)], _store())
    assert [e.outcome for e in record.entries] == ["failed", "not_attempted"]
    assert "db down" in record.entries[0].failure_code


async def test_scope_is_set_during_the_undo_and_cleared_after():
    calls: list = []
    _undo("undo_a", calls)
    register_instance("owner", _Agent("owner"))
    mid = uuid4()
    await _run([_step(0)], _store(), mid)
    assert calls[0][2] is not None
    assert calls[0][2].retried_message_id == mid
    assert current_rollback_scope() is None


async def test_scope_cleared_after_a_failure():
    _undo("undo_a", [], raises=RuntimeError("x"))
    register_instance("owner", _Agent("owner"))
    await _run([_step(0)], _store())
    assert current_rollback_scope() is None


async def test_uses_the_owning_agents_tool_deps():
    seen = []

    async def undo_dep(store, id: str) -> dict:
        seen.append((store, id))
        return {"ok": True}

    tool(
        access=ToolAccess.WRITE,
        description="d",
        reversibility=ToolReversibility.IRREVERSIBLE,
    )(undo_dep)
    register_instance("owner", _Agent("owner", {"store": "S"}))
    record = await _run([_step(0, undo_tool="undo_dep")], _store())
    assert seen == [("S", "0")]
    assert record.entries[0].outcome == "undone"


async def test_empty_plan_writes_nothing():
    store = _store()
    record = await _run([], store)
    assert record.entries == []
    store.set_rollback.assert_not_awaited()
