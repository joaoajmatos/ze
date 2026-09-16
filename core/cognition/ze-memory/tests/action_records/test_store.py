from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_plugin.contribution import Contribution, SourceFunction, TargetFace

from ze_memory.action_records.errors import (
    ActionRecordConflictError,
    ActionRecordNotFoundError,
)
from ze_memory.action_records.store import PostgresActionRecordStore
from ze_memory.action_records.types import (
    ActionLifecycle,
    ActionOutcome,
    ActionRecordDraft,
    AuthoritativeRef,
    CausalRef,
)


def _pool(fetchrow=None, fetch=None):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=fetchrow if callable(fetchrow) else None)
    if not callable(fetchrow):
        conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.fetch = AsyncMock(return_value=fetch or [])

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    return pool, conn


def _confidence() -> Confidence:
    return Confidence(value=1.0, decay_profile=DecayProfile.TIME_LINEAR)


def _draft(**overrides) -> ActionRecordDraft:
    base = dict(
        idempotency_key="key-1",
        action_type="workspace.run",
        actor="workspace",
        producer_plugin="ze-workspace",
        lifecycle=ActionLifecycle.SUCCEEDED,
        outcome=ActionOutcome.SUCCESS,
        occurred_at=datetime.now(timezone.utc),
        summary="workspace run succeeded",
        authoritative_ref=AuthoritativeRef(
            domain="workspace.runs", record_id=str(uuid4())
        ),
    )
    base.update(overrides)
    return ActionRecordDraft(**base)


def _contribution(draft: ActionRecordDraft) -> Contribution:
    return Contribution(
        claim_kind=ClaimKind.ACTION_RECORD,
        provenance=Provenance.PROMPT_SUPPLIED,
        confidence=_confidence(),
        target_face=TargetFace.WORLD,
        source_function=SourceFunction.ACTION,
        action_record=draft,
    )


def _row(draft: ActionRecordDraft, *, record_id=None):
    now = datetime.now(timezone.utc)
    return {
        "id": record_id or uuid4(),
        "idempotency_key": draft.idempotency_key,
        "action_type": draft.action_type,
        "actor": draft.actor,
        "producer_plugin": draft.producer_plugin,
        "lifecycle": draft.lifecycle.value,
        "outcome": None if draft.outcome is None else draft.outcome.value,
        "occurred_at": draft.occurred_at,
        "provenance": Provenance.PROMPT_SUPPLIED.value,
        "confidence": 1.0,
        "target_face": TargetFace.WORLD.value,
        "summary": draft.summary,
        "authoritative_domain": draft.authoritative_ref.domain,
        "authoritative_record_id": draft.authoritative_ref.record_id,
        "context": {},
        "evidence": [],
        "causal_refs": [],
        "retry_of": draft.retry_of,
        "supersedes": draft.supersedes,
        "failure_code": draft.failure_code,
        "created_at": now,
    }


async def test_append_inserts_once() -> None:
    draft = _draft()
    row = _row(draft)
    pool, conn = _pool(fetchrow=row)
    store = PostgresActionRecordStore(pool)
    record = await store.append(_contribution(draft))
    assert record.idempotency_key == "key-1"
    assert "INSERT INTO action_records" in conn.fetchrow.await_args.args[0]
    assert "UPDATE action_records" not in conn.fetchrow.await_args.args[0]


async def test_duplicate_key_returns_existing() -> None:
    draft = _draft()
    existing = _row(draft)
    values = [None, existing]

    async def fetchrow(*_args, **_kwargs):
        return values.pop(0)

    pool, _conn = _pool(fetchrow=fetchrow)
    store = PostgresActionRecordStore(pool)
    record = await store.append(_contribution(draft))
    assert record.id == existing["id"]


async def test_material_mismatch_is_rejected() -> None:
    draft = _draft(summary="workspace run succeeded")
    existing = _row(_draft(summary="different observation"))
    values = [None, existing]

    async def fetchrow(*_args, **_kwargs):
        return values.pop(0)

    pool, _conn = _pool(fetchrow=fetchrow)
    store = PostgresActionRecordStore(pool)
    with pytest.raises(ActionRecordConflictError):
        await store.append(_contribution(draft))


async def test_dangling_retry_of_is_rejected() -> None:
    missing = uuid4()
    pool, conn = _pool(fetchrow=None)
    store = PostgresActionRecordStore(pool)
    with pytest.raises(ActionRecordNotFoundError):
        await store.append(_contribution(_draft(retry_of=missing)))
    assert "SELECT * FROM action_records WHERE id" in conn.fetchrow.await_args.args[0]


async def test_list_by_authoritative_ref_uses_opaque_id() -> None:
    ref = AuthoritativeRef(domain="messenger.outbound", record_id="not-a-uuid")
    draft = _draft(authoritative_ref=ref)
    pool, conn = _pool(fetchrow=None, fetch=[_row(draft)])
    store = PostgresActionRecordStore(pool)
    rows = await store.list(authoritative_ref=ref)
    assert len(rows) == 1
    sql = conn.fetch.await_args.args[0]
    assert "authoritative_domain" in sql
    assert conn.fetch.await_args.args[1] == "messenger.outbound"
    assert conn.fetch.await_args.args[2] == "not-a-uuid"


async def test_list_by_causal_ref() -> None:
    causal = CausalRef(kind="goal", id=uuid4())
    pool, conn = _pool(fetch=[], fetchrow=None)
    store = PostgresActionRecordStore(pool)
    await store.list(causal_ref=causal)
    sql = conn.fetch.await_args.args[0]
    assert "causal_refs @>" in sql


async def test_started_row_has_no_outcome() -> None:
    draft = _draft(
        lifecycle=ActionLifecycle.STARTED,
        outcome=None,
        summary="workspace run started",
    )
    pool, _conn = _pool(fetchrow=_row(draft))
    store = PostgresActionRecordStore(pool)
    record = await store.append(_contribution(draft))
    assert record.outcome is None
    assert record.lifecycle is ActionLifecycle.STARTED


@pytest.mark.parametrize(
    ("lifecycle", "outcome", "failure_code"),
    [
        (ActionLifecycle.IN_PROGRESS, None, None),
        (ActionLifecycle.FAILED, ActionOutcome.FAILURE, "nonzero_exit"),
        (ActionLifecycle.CANCELLED, ActionOutcome.CANCELLED, None),
        (ActionLifecycle.PARTIAL, ActionOutcome.PARTIAL, None),
        (ActionLifecycle.TIMED_OUT, ActionOutcome.TIMEOUT, "timed_out"),
        (ActionLifecycle.UNKNOWN, ActionOutcome.UNKNOWN, "outcome_unobserved"),
    ],
)
async def test_lifecycle_observations_are_immutable(
    lifecycle: ActionLifecycle,
    outcome: ActionOutcome | None,
    failure_code: str | None,
) -> None:
    draft = _draft(
        lifecycle=lifecycle,
        outcome=outcome,
        failure_code=failure_code,
        summary=f"workspace run {lifecycle.value}",
        idempotency_key=f"key-{lifecycle.value}",
    )
    pool, conn = _pool(fetchrow=_row(draft))
    store = PostgresActionRecordStore(pool)
    record = await store.append(_contribution(draft))
    assert record.lifecycle is lifecycle
    assert record.outcome is outcome
    assert "UPDATE action_records" not in conn.fetchrow.await_args.args[0]
