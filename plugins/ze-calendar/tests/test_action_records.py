from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
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

from ze_calendar.action_records import configure_action_recorder
from ze_calendar.agents.calendar.tools import create_event, delete_event, update_event
from ze_calendar.agents.reminders.tools import cancel_reminder, set_reminder


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


def _calendar_credentials(result: dict | None = None, *, fail: Exception | None = None):
    service = MagicMock()
    execute = MagicMock()
    if fail is not None:
        execute.side_effect = fail
    else:
        execute.return_value = result or {"id": "evt-1", "htmlLink": "https://cal"}
    service.events.return_value.insert.return_value.execute = execute
    service.events.return_value.update.return_value.execute = execute
    service.events.return_value.delete.return_value.execute = execute
    service.events.return_value.get.return_value.execute.return_value = {
        "id": "evt-1",
        "summary": "old",
        "start": {"dateTime": "2026-09-16T10:00:00Z"},
        "end": {"dateTime": "2026-09-16T11:00:00Z"},
    }
    creds = MagicMock()
    creds.calendar.return_value = service
    return creds


async def test_create_event_success_cites_provider_id(ledger: InMemoryActionRecordStore):
    result = await create_event(
        credentials=_calendar_credentials(),
        summary="Dentist",
        start="2026-09-16T10:00:00Z",
        end="2026-09-16T11:00:00Z",
    )
    assert result["id"] == "evt-1"
    record = next(iter(ledger.by_key.values()))
    assert record.lifecycle is ActionLifecycle.SUCCEEDED
    assert record.outcome is ActionOutcome.SUCCESS
    assert record.authoritative_ref.record_id == "evt-1"
    assert record.authoritative_ref.domain == "calendar.event"


async def test_create_event_failure_without_id_does_not_fabricate_source(
    ledger: InMemoryActionRecordStore,
):
    with pytest.raises(RuntimeError):
        await create_event(
            credentials=_calendar_credentials(fail=RuntimeError("provider down")),
            summary="Dentist",
            start="2026-09-16T10:00:00Z",
            end="2026-09-16T11:00:00Z",
        )
    assert ledger.by_key == {}


async def test_update_and_delete_record_outcomes(ledger: InMemoryActionRecordStore):
    await update_event(
        credentials=_calendar_credentials({"id": "evt-1"}),
        event_id="evt-1",
        summary="Updated",
    )
    await delete_event(credentials=_calendar_credentials({}), event_id="evt-1")
    kinds = {r.action_type for r in ledger.by_key.values()}
    assert "calendar.update" in kinds
    assert "calendar.delete" in kinds


async def test_calendar_replay_is_idempotent(ledger: InMemoryActionRecordStore):
    creds = _calendar_credentials()
    await create_event(
        credentials=creds,
        summary="Dentist",
        start="2026-09-16T10:00:00Z",
        end="2026-09-16T11:00:00Z",
    )
    await create_event(
        credentials=creds,
        summary="Dentist",
        start="2026-09-16T10:00:00Z",
        end="2026-09-16T11:00:00Z",
    )
    assert len(ledger.by_key) == 1


async def test_set_reminder_records_success(ledger: InMemoryActionRecordStore):
    rid = uuid4()
    store = AsyncMock()
    store.create = AsyncMock(return_value=rid)
    scheduler = MagicMock()
    fire_at = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    result = await set_reminder(
        store=store,
        scheduler=scheduler,
        notifier=AsyncMock(),
        label="Meds",
        fire_at=fire_at,
    )
    assert result["id"] == str(rid)
    record = next(iter(ledger.by_key.values()))
    assert record.lifecycle is ActionLifecycle.SUCCEEDED
    assert record.authoritative_ref.record_id == str(rid)
    assert record.context.reminder_id == rid


async def test_cancel_reminder_is_cancelled_not_failure(
    ledger: InMemoryActionRecordStore,
):
    rid = uuid4()
    reminder = MagicMock()
    reminder.label = "Meds"
    store = AsyncMock()
    store.get = AsyncMock(return_value=reminder)
    store.delete = AsyncMock()
    scheduler = MagicMock()
    result = await cancel_reminder(store=store, scheduler=scheduler, reminder_id=str(rid))
    assert result["cancelled"] == "Meds"
    record = next(iter(ledger.by_key.values()))
    assert record.lifecycle is ActionLifecycle.CANCELLED
    assert record.outcome is ActionOutcome.CANCELLED
