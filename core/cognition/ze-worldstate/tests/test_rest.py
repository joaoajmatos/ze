from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4


from ze_worldstate import rest
from ze_worldstate.types import (
    LoopClaimKind,
    LoopProvenance,
    LoopSource,
    LoopSourceRole,
    LoopState,
    OpenLoop,
    SourceKey,
)

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)


def _loop(**overrides) -> OpenLoop:
    defaults = dict(
        id=uuid4(),
        title="Sort out the deposit with the landlord",
        claim_kind=LoopClaimKind.SUSPICION,
        provenance=LoopProvenance.CONVERSATION,
        confidence=0.3,
        state=LoopState.SUSPECTED,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return OpenLoop(**defaults)


def _source(
    loop_id,
    *,
    role=LoopSourceRole.CORROBORATION,
    inflow="email",
    ref="G1",
    evidence=None,
    same_concern=None,
    promoted=False,
    minutes=0,
) -> LoopSource:
    return LoopSource(
        loop_id=loop_id,
        role=role,
        key=SourceKey(inflow, ref),
        evidence=evidence,
        same_concern=same_concern,
        promoted=promoted,
        created_at=NOW + timedelta(minutes=minutes),
    )


async def test_list_loops_adds_promoted_and_source_inflows_in_one_query():
    loop = _loop()
    other = _loop(id=uuid4(), title="No sources here")
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[loop, other])
    loop_store.list_sources_for = AsyncMock(
        return_value={
            loop.id: [
                _source(
                    loop.id, role=LoopSourceRole.ORIGIN, inflow="conversation", ref="T1"
                ),
                _source(
                    loop.id, inflow="email", ref="G1", same_concern=0.93, promoted=True
                ),
            ]
        }
    )

    items = await rest.list_loops(loop_store)

    loop_store.list_sources_for.assert_awaited_once_with([loop.id, other.id])
    assert items[0]["promoted"] is True
    assert items[0]["source_inflows"] == ["conversation", "email"]
    assert items[1]["promoted"] is False
    assert items[1]["source_inflows"] == []


async def test_list_loops_source_inflows_are_distinct_and_first_seen_order():
    loop = _loop()
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[loop])
    loop_store.list_sources_for = AsyncMock(
        return_value={
            loop.id: [
                _source(
                    loop.id, role=LoopSourceRole.ORIGIN, inflow="conversation", ref="T1"
                ),
                _source(loop.id, inflow="email", ref="G1", minutes=1),
                _source(loop.id, inflow="conversation", ref="T2", minutes=2),
            ]
        }
    )

    items = await rest.list_loops(loop_store)

    assert items[0]["source_inflows"] == ["conversation", "email"]


async def test_list_loops_not_promoted_when_no_corroboration_promoted():
    loop = _loop()
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[loop])
    loop_store.list_sources_for = AsyncMock(
        return_value={
            loop.id: [
                _source(
                    loop.id, role=LoopSourceRole.ORIGIN, inflow="conversation", ref="T1"
                ),
                _source(
                    loop.id, inflow="email", ref="G1", same_concern=0.8, promoted=False
                ),
            ]
        }
    )

    items = await rest.list_loops(loop_store)

    assert items[0]["promoted"] is False


async def test_list_loops_empty_list_skips_the_source_query():
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[])
    loop_store.list_sources_for = AsyncMock(return_value={})

    items = await rest.list_loops(loop_store)

    assert items == []
    loop_store.list_sources_for.assert_awaited_once_with([])


async def test_list_exposes_reminder_and_goal_ids():
    reminder_id, goal_id = uuid4(), uuid4()
    loop = _loop(reminder_id=reminder_id, goal_id=goal_id)
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[loop])
    loop_store.list_sources_for = AsyncMock(return_value={})

    (item,) = await rest.list_loops(loop_store)

    assert item["reminder_id"] == reminder_id
    assert item["goal_id"] == goal_id


async def test_unlinked_loop_has_null_ids():
    loop = _loop()
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[loop])
    loop_store.list_sources_for = AsyncMock(return_value={})
    (item,) = await rest.list_loops(loop_store)
    assert item["reminder_id"] is None and item["goal_id"] is None


async def test_list_exposes_confidence_movement_and_timing():
    changed = NOW + timedelta(hours=1)
    loop = _loop(
        confidence_prior=0.4,
        confidence_changed_at=changed,
        drift_deadline=NOW + timedelta(days=7),
        confirmed_at=NOW,
    )
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[loop])
    loop_store.list_sources_for = AsyncMock(return_value={})

    (item,) = await rest.list_loops(loop_store)

    assert item["confidence_prior"] == 0.4
    assert item["confidence_changed_at"] == changed.isoformat()
    assert item["drift_deadline"] == (NOW + timedelta(days=7)).isoformat()
    assert item["confirmed_at"] == NOW.isoformat()


async def test_never_changed_loop_has_null_movement():
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[_loop()])
    loop_store.list_sources_for = AsyncMock(return_value={})

    (item,) = await rest.list_loops(loop_store)

    for key in ("confidence_prior", "confidence_changed_at", "drift_deadline", "confirmed_at"):
        assert item[key] is None
