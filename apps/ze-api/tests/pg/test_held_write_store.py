import uuid
from datetime import timedelta

import pytest
from ze_automation.holds.store import PostgresHeldWriteStore
from ze_automation.holds.types import HeldWrite, HeldWriteStatus

from tests.pg._builders import utcnow

pytestmark = pytest.mark.pg


def _hold(**overrides) -> HeldWrite:
    fields = {
        "request_id": f"req-{uuid.uuid4().hex}",
        "source": "workflow",
        "owner_ref": "exec-1",
        "items": [{"item_id": "a", "effect": "Send an email"}],
        "payload": {"thread_id": "t-1"},
        "expires_at": utcnow() + timedelta(hours=24),
    }
    fields.update(overrides)
    return HeldWrite(**fields)


async def test_create_then_get_round_trips_jsonb(pg_pool):
    store = PostgresHeldWriteStore(pg_pool)
    hold = _hold()

    await store.create(hold)
    loaded = await store.get(hold.request_id)

    assert loaded is not None
    assert loaded.status is HeldWriteStatus.OPEN
    assert loaded.items == hold.items
    assert loaded.payload == hold.payload
    assert loaded.decided_at is None


async def test_decide_twice_second_call_returns_false(pg_pool):
    store = PostgresHeldWriteStore(pg_pool)
    hold = _hold()
    await store.create(hold)

    assert await store.decide(hold.request_id, HeldWriteStatus.APPROVED) is True
    assert await store.decide(hold.request_id, HeldWriteStatus.DENIED) is False

    loaded = await store.get(hold.request_id)
    assert loaded.status is HeldWriteStatus.APPROVED
    assert loaded.decided_at is not None


async def test_list_expired_returns_only_open_holds_past_deadline(pg_pool):
    store = PostgresHeldWriteStore(pg_pool)
    overdue = _hold(expires_at=utcnow() - timedelta(minutes=1))
    fresh = _hold(expires_at=utcnow() + timedelta(hours=1))
    await store.create(overdue)
    await store.create(fresh)

    expired_ids = {h.request_id for h in await store.list_expired(utcnow())}

    assert overdue.request_id in expired_ids
    assert fresh.request_id not in expired_ids
