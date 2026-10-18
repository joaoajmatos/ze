"""Script learning: one ledger row per run, a candidate on the third success."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from ze_agents.scripts import ScriptOutcome
from ze_memory.action_records.types import (
    ActionLifecycle,
    ActionOutcome,
)
from ze_memory.procedures.types import ProcedureSourceKind

from ze_workspace.script_learning import ScriptLearning, tool_signature


class FakeLedger:
    """Enforces the real idempotency key and answers list_by_script_key."""

    def __init__(self) -> None:
        self.rows: dict[str, SimpleNamespace] = {}

    async def append(self, contribution):
        draft = contribution.action_record
        if draft.idempotency_key in self.rows:
            return self.rows[draft.idempotency_key]
        record = SimpleNamespace(
            id=uuid4(),
            idempotency_key=draft.idempotency_key,
            lifecycle=draft.lifecycle,
            outcome=draft.outcome,
            failure_code=draft.failure_code,
            actor=draft.actor,
            summary=draft.summary,
            context=draft.context,
            action_type=draft.action_type,
            authoritative_ref=draft.authoritative_ref,
            occurred_at=draft.occurred_at,
            seq=len(self.rows),
        )
        self.rows[draft.idempotency_key] = record
        return record

    async def get(self, record_id):
        return next((r for r in self.rows.values() if r.id == record_id), None)

    async def list(self, **kwargs):
        return []

    async def list_by_script_key(self, script_key, limit=3):
        mine = [r for r in self.rows.values() if r.context.script_key == script_key]
        return sorted(mine, key=lambda r: r.seq, reverse=True)[:limit]


def make_learning(ledger=None, admission=None):
    ledger = ledger or FakeLedger()
    admission = admission or AsyncMock()
    admission.candidate_exists = AsyncMock(return_value=False)
    admission.submit_procedure_candidate = AsyncMock()
    return ScriptLearning(action_record_store=ledger, admission=admission), ledger, admission


async def run(learning, *, status="ok", tools=("get_a", "get_b"), agent="finance", **kw):
    await learning.record(
        script_id=str(kw.pop("script_id", uuid4())),
        agent=agent,
        source=kw.pop("source", "z.finish(1)"),
        outcome=ScriptOutcome(status=status, exception=kw.pop("exception", None)),
        tools=list(tools),
        **kw,
    )


async def test_every_run_appends_its_own_record():
    learning, ledger, _ = make_learning()
    for _ in range(3):
        await run(learning)
    assert len(ledger.rows) == 3
    key = tool_signature("finance", ["get_a", "get_b"])
    assert {r.context.script_key for r in ledger.rows.values()} == {key}


async def test_record_fields_for_success_failure_and_timeout():
    learning, ledger, _ = make_learning()
    await run(learning, status="ok")
    await run(learning, status="exception", exception="KeyError")
    await run(learning, status="timeout")
    await run(learning, status="resource_limit")
    rows = sorted(ledger.rows.values(), key=lambda r: r.seq)
    ok, exc, timeout, limit = rows
    assert (ok.lifecycle, ok.outcome, ok.failure_code) == (
        ActionLifecycle.SUCCEEDED,
        ActionOutcome.SUCCESS,
        None,
    )
    assert (exc.lifecycle, exc.outcome, exc.failure_code) == (
        ActionLifecycle.FAILED,
        ActionOutcome.FAILURE,
        "exception",
    )
    assert (timeout.lifecycle, timeout.outcome, timeout.failure_code) == (
        ActionLifecycle.TIMED_OUT,
        ActionOutcome.TIMEOUT,
        "timeout",
    )
    assert limit.failure_code == "resource_limit"
    assert ok.action_type == "workspace.run"
    assert ok.authoritative_ref.domain == "workspace.tool_script"
    assert ok.actor == "finance"
    assert ok.summary == "Script by finance: 2 tool calls"


async def test_third_consecutive_success_submits_one_candidate():
    learning, _, admission = make_learning()
    await run(learning, source="old")
    await run(learning, source="mid")
    admission.submit_procedure_candidate.assert_not_awaited()
    await run(learning, source="latest", user_turn="x" * 300)
    admission.submit_procedure_candidate.assert_awaited_once()
    cand = admission.submit_procedure_candidate.await_args.args[0]
    key = tool_signature("finance", ["get_a", "get_b"])
    assert cand.source_kind is ProcedureSourceKind.TOOL_SCRIPT
    assert cand.name == f"Script: get_a → get_b [{key[:8]}]"
    assert len(cand.name) <= 120
    assert cand.steps == ["latest"]
    assert cand.preconditions == []
    assert cand.limits == ["get_a", "get_b"]
    assert cand.success_criteria == ["script ends ok"]
    assert cand.trigger == "x" * 120
    assert len(cand.evidence_refs) == 3
    assert all(e.kind == "action_record" and isinstance(e.id, UUID) for e in cand.evidence_refs)


async def test_fourth_success_submits_nothing_when_candidate_exists():
    learning, _, admission = make_learning()
    for _ in range(3):
        await run(learning)
    admission.candidate_exists = AsyncMock(return_value=True)
    await run(learning)
    assert admission.submit_procedure_candidate.await_count == 1


async def test_failure_resets_the_run():
    learning, _, admission = make_learning()
    await run(learning)
    await run(learning)
    await run(learning, status="exception")
    await run(learning)
    admission.submit_procedure_candidate.assert_not_awaited()


async def test_agents_with_the_same_tools_do_not_combine():
    learning, _, admission = make_learning()
    await run(learning, agent="finance")
    await run(learning, agent="messenger")
    await run(learning, agent="finance")
    await run(learning, agent="messenger")
    admission.submit_procedure_candidate.assert_not_awaited()


async def test_procedure_run_never_submits():
    learning, ledger, admission = make_learning()
    for _ in range(4):
        await run(learning, procedure_id=str(uuid4()))
    assert len(ledger.rows) == 4
    admission.submit_procedure_candidate.assert_not_awaited()


async def test_no_tools_means_nothing_to_learn():
    learning, _, admission = make_learning()
    for _ in range(3):
        await run(learning, tools=[])
    admission.submit_procedure_candidate.assert_not_awaited()


async def test_store_error_is_logged_never_raised():
    ledger = FakeLedger()
    ledger.append = AsyncMock(side_effect=RuntimeError("db down"))
    learning, _, admission = make_learning(ledger)
    await run(learning)
    admission.submit_procedure_candidate.assert_not_awaited()


async def test_admission_error_is_logged_never_raised():
    learning, _, admission = make_learning()
    admission.submit_procedure_candidate = AsyncMock(side_effect=RuntimeError("no"))
    for _ in range(3):
        await run(learning)


def test_signature_is_stable_and_ordered():
    a = tool_signature("finance", ["x", "y", "x"])
    assert a == tool_signature("finance", ["x", "y"])
    assert a != tool_signature("finance", ["y", "x"])
    assert a != tool_signature("other", ["x", "y"])
    assert len(a) == 64
