from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_agents.screen import ResolveContext, ScreenRef, ScreenStatus
from ze_proactive.notification_store import NotificationStore
from ze_proactive.screen_resolvers import NotificationScreenResolver
from ze_proactive.types import NotificationRow

NOW = datetime(2026, 10, 17, 14, 0, tzinfo=UTC)
CTX = ResolveContext(now=NOW)


def _row(**kw) -> NotificationRow:
    base = dict(
        id=str(uuid4()),
        event_type="workflow_failure",
        source="workflows",
        title="Weekly report failed",
        body="b",
        target_type="workflow_execution",
        target_id="e1",
        target_parent_id="w1",
        created_at=NOW - timedelta(hours=3),
        read_at=None,
        push_class="accountability",
        urgency="high",
        format="text",
        actions=[],
        delivery="delivered",
        delivered_at=None,
    )
    base.update(kw)
    return NotificationRow(**base)


async def test_notification_line_carries_its_target_ref_with_parent():
    row = _row()
    store = AsyncMock()
    store.get = AsyncMock(return_value=row)
    [line] = await NotificationScreenResolver(store).resolve(
        [ScreenRef(kind="notification", id=row.id)], CTX
    )
    assert line.label == "Weekly report failed" and "3 h ago" in line.summary
    assert (line.target.kind, line.target.id, line.target.parent_id) == (
        "workflow_execution",
        "e1",
        "w1",
    )


async def test_no_target_when_the_row_has_none_and_missing_when_gone():
    row = _row(target_type=None, target_id=None, target_parent_id=None)
    store = AsyncMock()
    store.get = AsyncMock(return_value=row)
    [line] = await NotificationScreenResolver(store).resolve(
        [ScreenRef(kind="notification", id=row.id)], CTX
    )
    assert line.target is None
    store.get = AsyncMock(return_value=None)
    [gone] = await NotificationScreenResolver(store).resolve(
        [ScreenRef(kind="notification", id="x")], CTX
    )
    assert gone.status is ScreenStatus.MISSING


async def test_store_get_maps_a_row_and_rejects_bad_ids():
    row = MagicMock()
    data = _row()
    row.__getitem__ = lambda self, key: {
        "id": data.id,
        "event_type": data.event_type,
        "source": data.source,
        "title": data.title,
        "body": data.body,
        "target_type": data.target_type,
        "target_id": data.target_id,
        "target_parent_id": data.target_parent_id,
        "created_at": data.created_at,
        "read_at": None,
        "push_class": data.push_class,
        "urgency": data.urgency,
        "format": data.format,
        "actions": "[]",
        "delivery": data.delivery,
        "delivered_at": None,
    }[key]
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=row)
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    store = NotificationStore(pool)
    got = await store.get(data.id)
    assert got is not None and got.target_parent_id == "w1"
    assert await store.get("nope") is None


async def test_every_written_target_type_resolves_or_is_dropped():
    from ze_proactive.screen_resolvers import TARGET_KIND

    store = AsyncMock()
    for target_type in (
        "open_loop",
        "person",
        "project",
        "entity",
        "fact",
        "goal",
        "goal_gate",
        "hypothesis",
        "reminder",
        "workspace_run",
        "held_write",
        "workflow_execution",
        "episode",
        "insight",
        "goal_suggestion",
        "chat_thread",
        "unknown",
    ):
        row = _row(target_type=target_type, target_id="x", target_parent_id=None)
        store.get = AsyncMock(return_value=row)
        (line,) = await NotificationScreenResolver(store).resolve(
            [ScreenRef(kind="notification", id=row.id)], CTX
        )
        if target_type in TARGET_KIND:
            assert line.target is not None
            assert line.target.kind == TARGET_KIND[target_type]
        else:
            assert line.target is None, target_type
