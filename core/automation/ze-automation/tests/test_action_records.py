from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from ze_plugin.contribution import Contribution
from ze_memory.action_records.types import (
    ActionLifecycle,
    ActionOutcome,
    ActionRecord,
    ActionRecordDraft,
)

from ze_automation.action_records import configure_action_recorder
from ze_automation.goals.postgres import PostgresGoalStore
from ze_automation.goals.types import ExecutionTrace
from ze_automation.workflow.postgres import PostgresWorkflowStore


class InMemoryActionRecordStore:
    def __init__(self) -> None:
        self.by_id: dict[UUID, ActionRecord] = {}
        self.by_key: dict[str, ActionRecord] = {}
        self.lock = asyncio.Lock()

    async def append(self, contribution: Contribution) -> ActionRecord:
        draft: ActionRecordDraft = contribution.action_record
        async with self.lock:
            existing = self.by_key.get(draft.idempotency_key)
            if existing is not None:
                return existing
            record = ActionRecord(
                id=uuid4(),
                idempotency_key=draft.idempotency_key,
                action_type=draft.action_type,
                actor=draft.actor,
                producer_plugin=draft.producer_plugin,
                lifecycle=draft.lifecycle,
                outcome=draft.outcome,
                occurred_at=draft.occurred_at,
                provenance=contribution.provenance,
                confidence=contribution.confidence,
                target_face=contribution.target_face,
                summary=draft.summary,
                authoritative_ref=draft.authoritative_ref,
                context=draft.context,
                evidence=list(contribution.evidence),
                causal_refs=list(draft.causal_refs),
                retry_of=draft.retry_of,
                supersedes=draft.supersedes,
                failure_code=draft.failure_code,
            )
            self.by_id[record.id] = record
            self.by_key[record.idempotency_key] = record
            return record

    async def get(self, record_id: UUID) -> ActionRecord | None:
        return self.by_id.get(record_id)

    async def list(self, **_kwargs) -> list[ActionRecord]:
        return list(self.by_id.values())


@pytest.fixture
def ledger():
    store = InMemoryActionRecordStore()
    configure_action_recorder(store)
    yield store
    configure_action_recorder(None)


def _pool(fetchrow=None, execute=None):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value=execute)
    conn.executemany = AsyncMock()

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    return pool, conn


def _trace(**overrides) -> ExecutionTrace:
    base = dict(
        milestone_id=uuid4(),
        goal_id=uuid4(),
        seq=0,
        tool_name="search_web",
        args={"query": "test"},
        result="ok",
        duration_ms=10,
        success=True,
        error=None,
    )
    base.update(overrides)
    return ExecutionTrace(**base)


async def test_save_traces_records_success_and_failure(ledger: InMemoryActionRecordStore):
    pool, _ = _pool()
    store = PostgresGoalStore(pool)
    ok = _trace(success=True)
    bad = _trace(success=False, error="boom", seq=1)
    await store.save_traces([ok, bad])
    assert len(ledger.by_key) == 2
    by_outcome = {r.outcome: r for r in ledger.by_key.values()}
    assert ActionOutcome.SUCCESS in by_outcome
    assert ActionOutcome.FAILURE in by_outcome
    success = by_outcome[ActionOutcome.SUCCESS]
    assert success.context.goal_id == ok.goal_id
    assert success.context.milestone_id == ok.milestone_id
    assert success.authoritative_ref.domain == "goal.goal_execution_trace"


async def test_save_traces_replay_is_idempotent(ledger: InMemoryActionRecordStore):
    pool, _ = _pool()
    store = PostgresGoalStore(pool)
    traces = [_trace()]
    await store.save_traces(traces)
    await store.save_traces(traces)
    assert len(ledger.by_key) == 1


async def test_workflow_start_then_finish_is_causally_linked(
    ledger: InMemoryActionRecordStore,
):
    execution_id = uuid4()
    workflow_id = uuid4()
    pool, conn = _pool(fetchrow={"id": execution_id, "steps": []})
    store = PostgresWorkflowStore(pool)
    started = await store.start_execution(workflow_id)
    assert started == execution_id
    await store.finish_execution(execution_id, "cancelled")
    started_rec = next(
        r for r in ledger.by_key.values() if r.lifecycle is ActionLifecycle.STARTED
    )
    cancelled = next(
        r for r in ledger.by_key.values() if r.lifecycle is ActionLifecycle.CANCELLED
    )
    assert cancelled.outcome is ActionOutcome.CANCELLED
    assert any(ref.id == started_rec.id for ref in cancelled.causal_refs)
    conn.execute.assert_awaited()


async def test_workflow_finish_replay_is_idempotent(ledger: InMemoryActionRecordStore):
    execution_id = uuid4()
    pool, _ = _pool()
    store = PostgresWorkflowStore(pool)
    await store.finish_execution(execution_id, "completed")
    await store.finish_execution(execution_id, "completed")
    assert len(ledger.by_key) == 1
    record = next(iter(ledger.by_key.values()))
    assert record.lifecycle is ActionLifecycle.SUCCEEDED
