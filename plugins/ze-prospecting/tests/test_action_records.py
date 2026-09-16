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

from ze_prospecting.action_records import configure_action_recorder
from ze_prospecting.store import ProspectCampaignStore


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


def _pool(fetchrow=None):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.execute = AsyncMock()

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    return pool, conn


async def test_add_outreach_records_pending(ledger: InMemoryActionRecordStore):
    outreach_id = uuid4()
    pool, _ = _pool(fetchrow={"id": outreach_id})
    store = ProspectCampaignStore(pool)
    result = await store.add_outreach(uuid4(), uuid4(), "email")
    assert result == outreach_id
    record = next(iter(ledger.by_key.values()))
    assert record.lifecycle is ActionLifecycle.IN_PROGRESS
    assert record.outcome is None
    assert record.authoritative_ref.record_id == str(outreach_id)
    assert record.context.outreach_id == outreach_id


async def test_log_outreach_sent_and_bounced(ledger: InMemoryActionRecordStore):
    outreach_id = uuid4()
    pool, _ = _pool()
    store = ProspectCampaignStore(pool)
    await store.log_outreach_event(outreach_id, "sent", "intro", "sent_at")
    await store.log_outreach_event(outreach_id, "bounced", "hard bounce", None)
    by_lifecycle = {r.lifecycle: r for r in ledger.by_key.values()}
    assert by_lifecycle[ActionLifecycle.SUCCEEDED].outcome is ActionOutcome.SUCCESS
    assert by_lifecycle[ActionLifecycle.FAILED].outcome is ActionOutcome.FAILURE
    assert by_lifecycle[ActionLifecycle.FAILED].failure_code == "bounced"


async def test_outreach_pending_then_sent_is_causally_linked(
    ledger: InMemoryActionRecordStore,
):
    outreach_id = uuid4()
    pool, _ = _pool(fetchrow={"id": outreach_id})
    store = ProspectCampaignStore(pool)
    await store.add_outreach(uuid4(), uuid4(), "email")
    await store.log_outreach_event(outreach_id, "sent", "intro", "sent_at")
    pending = next(
        r for r in ledger.by_key.values() if r.lifecycle is ActionLifecycle.IN_PROGRESS
    )
    sent = next(
        r for r in ledger.by_key.values() if r.lifecycle is ActionLifecycle.SUCCEEDED
    )
    assert any(ref.id == pending.id for ref in sent.causal_refs)


async def test_outreach_replay_is_idempotent(ledger: InMemoryActionRecordStore):
    outreach_id = uuid4()
    pool, _ = _pool()
    store = ProspectCampaignStore(pool)
    await store.log_outreach_event(outreach_id, "sent", "intro", "sent_at")
    await store.log_outreach_event(outreach_id, "sent", "intro", "sent_at")
    assert len(ledger.by_key) == 1
