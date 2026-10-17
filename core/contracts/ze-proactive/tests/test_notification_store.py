from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_proactive.notification_store import NotificationStore


def _make_row(
    *,
    id_=None,
    event_type="stuck_goal",
    source="goals",
    title="Goal stuck",
    body="Goal A hasn't moved in 3 days",
    target_type="goal",
    target_id="goal-a",
    target_parent_id=None,
    created_at=None,
    read_at=None,
    push_class="accountability",
    delivery="delivered",
):
    return {
        "id": id_ or uuid4(),
        "event_type": event_type,
        "source": source,
        "title": title,
        "body": body,
        "target_type": target_type,
        "target_id": target_id,
        "target_parent_id": target_parent_id,
        "created_at": created_at or datetime.now(timezone.utc),
        "read_at": read_at,
        "push_class": push_class,
        "urgency": "normal",
        "format": "text",
        "actions": "[]",
        "delivery": delivery,
        "delivered_at": None,
    }


def make_conn(rows=None, fetchrow_result=None, execute_result="UPDATE 0"):
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows or [])
    conn.fetchrow = AsyncMock(return_value=fetchrow_result)
    conn.execute = AsyncMock(return_value=execute_result)
    tx_cm = AsyncMock()
    tx_cm.__aenter__ = AsyncMock(return_value=None)
    tx_cm.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx_cm)
    return conn


def make_pool(conn=None):
    if conn is None:
        conn = make_conn()
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=cm)
    return pool


def make_store(conn=None):
    c = conn or make_conn()
    return NotificationStore(pool=make_pool(c)), c


# ── create ──────────────────────────────────────────────────────────────────


async def test_create_inserts_and_returns_row():
    row = _make_row(event_type="workflow_failure", source="workflows")
    conn = make_conn()
    conn.fetchrow = AsyncMock(return_value=row)
    store, conn = make_store(conn)

    result = await store.create(
        event_type="workflow_failure",
        source="workflows",
        title="Run failed",
        body="Workflow X failed",
        target_type="workflow_execution",
        target_id="run-1",
        target_parent_id="wf-1",
        push_class="accountability",
        urgency="high",
        format="text",
        actions=[],
        delivery="delivered",
    )

    assert result.event_type == "workflow_failure"
    assert result.read_at is None
    sql, *params = conn.fetchrow.call_args.args
    assert "target_parent_id" in sql
    assert "wf-1" in params


async def test_create_persists_the_parent_it_is_given():
    conn = make_conn()
    conn.fetchrow = AsyncMock(
        return_value=_make_row(target_type="goal_gate", target_parent_id="goal-1")
    )
    store, _ = make_store(conn)

    result = await store.create(
        event_type="goal_gate",
        source="goals",
        title="t",
        body="b",
        target_type="goal_gate",
        target_id="gate-1",
        target_parent_id="goal-1",
        push_class="accountability",
        urgency="normal",
        format="text",
        actions=[],
        delivery="delivered",
    )

    assert result.target_parent_id == "goal-1"


async def test_list_page_and_list_held_return_the_parent():
    rows = [_make_row(target_type="workflow_execution", target_parent_id="wf-9")]
    store, conn = make_store(make_conn(rows))

    items, _ = await store.list_page()
    held = await store.list_held()

    assert items[0].target_parent_id == "wf-9"
    assert held[0].target_parent_id == "wf-9"
    assert "target_parent_id" in conn.fetch.call_args.args[0]


async def test_a_notification_without_a_parent_lists_none():
    store, _ = make_store(make_conn([_make_row()]))
    items, _ = await store.list_page()
    assert items[0].target_parent_id is None


# ── list_page (pagination) ─────────────────────────────────────────────────


async def test_list_page_returns_items_and_no_cursor_when_exhausted():
    rows = [_make_row(title=f"N{i}") for i in range(3)]
    store, conn = make_store(make_conn(rows))

    items, next_cursor = await store.list_page(limit=20)

    assert len(items) == 3
    assert next_cursor is None


async def test_list_page_returns_cursor_when_more_pages_exist():
    rows = [_make_row(title=f"N{i}") for i in range(21)]
    store, conn = make_store(make_conn(rows))

    items, next_cursor = await store.list_page(limit=20)

    assert len(items) == 20
    assert next_cursor is not None


async def test_list_page_unread_only_adds_condition():
    store, conn = make_store(make_conn([]))

    await store.list_page(unread_only=True)

    sql = conn.fetch.call_args.args[0]
    assert "read_at IS NULL" in sql


async def test_list_page_mark_read_marks_returned_page():
    rows = [_make_row(read_at=None)]
    store, conn = make_store(make_conn(rows))

    items, _ = await store.list_page(mark_read=True)

    assert items[0].read is True
    conn.execute.assert_called_once()


async def test_list_page_no_mark_read_skips_update():
    rows = [_make_row(read_at=None)]
    store, conn = make_store(make_conn(rows))

    items, _ = await store.list_page(mark_read=False)

    assert items[0].read is False
    conn.execute.assert_not_called()


# ── unread_count ────────────────────────────────────────────────────────────


async def test_unread_count_returns_int():
    conn = make_conn()
    conn.fetchrow = AsyncMock(return_value=[5])
    store, _ = make_store(conn)

    count = await store.unread_count()

    assert count == 5


# ── mark_read / mark_all_read ──────────────────────────────────────────────


async def test_mark_read_returns_true_when_updated():
    conn = make_conn(execute_result="UPDATE 1")
    store, _ = make_store(conn)

    result = await store.mark_read(str(uuid4()))

    assert result is True


async def test_mark_read_returns_false_when_id_not_found():
    conn = make_conn(execute_result="UPDATE 0", fetchrow_result=None)
    store, _ = make_store(conn)

    result = await store.mark_read(str(uuid4()))

    assert result is False


async def test_mark_read_returns_true_when_already_read():
    conn = make_conn(execute_result="UPDATE 0", fetchrow_result={"1": 1})
    store, _ = make_store(conn)

    result = await store.mark_read(str(uuid4()))

    assert result is True


async def test_mark_all_read_returns_count():
    conn = make_conn(execute_result="UPDATE 4")
    store, _ = make_store(conn)

    result = await store.mark_all_read()

    assert result == 4


# ── exists_recent (dedup, research R3) ─────────────────────────────────────


async def test_exists_recent_true_when_row_found():
    conn = make_conn()
    conn.fetchrow = AsyncMock(return_value={"1": 1})
    store, _ = make_store(conn)

    result = await store.exists_recent(
        event_type="stuck_goal", target_type="goal", target_id="goal-a", hours=24
    )

    assert result is True


async def test_exists_recent_false_when_no_row():
    store, _ = make_store(make_conn())

    result = await store.exists_recent(
        event_type="stuck_goal", target_type="goal", target_id="goal-a", hours=24
    )

    assert result is False


async def test_exists_recent_scoped_by_target_not_just_event_type():
    """Same event_type but different target must not dedup against each other."""
    conn = make_conn()
    store, _ = make_store(conn)

    await store.exists_recent(
        event_type="stuck_goal", target_type="goal", target_id="goal-a", hours=24
    )

    call_args = conn.fetchrow.call_args.args
    assert "goal-a" in call_args


# ── prune_read_older_than ──────────────────────────────────────────────────


async def test_prune_read_older_than_returns_pruned_count():
    conn = make_conn(execute_result="DELETE 7")
    store, _ = make_store(conn)

    result = await store.prune_read_older_than(days=90)

    assert result == 7
    call_args = conn.execute.call_args.args
    assert 90 in call_args


async def test_prune_read_older_than_only_targets_read_rows_past_cutoff():
    """Unread rows must never be touched; only read rows older than the window."""
    conn = make_conn(execute_result="DELETE 0")
    store, _ = make_store(conn)

    await store.prune_read_older_than(days=90)

    sql = conn.execute.call_args.args[0]
    assert "read_at IS NOT NULL" in sql
    assert "read_at < NOW()" in sql


# ── governor columns (phase 177) ───────────────────────────────────────────


async def test_create_writes_governor_columns():
    conn = make_conn()
    conn.fetchrow = AsyncMock(return_value=_make_row(push_class="discretionary"))
    store, conn = make_store(conn)

    result = await store.create(
        event_type="insight",
        source="personal",
        title="t",
        body="b",
        target_type=None,
        target_id=None,
        push_class="discretionary",
        urgency="low",
        format="html",
        actions=[{"label": "Go", "payload": "p", "row": 0}],
        delivery="held",
    )

    sql, *args = conn.fetchrow.call_args.args
    assert "push_class" in sql and "delivery" in sql and "delivered_at" in sql
    assert "discretionary" in args and "low" in args and "html" in args
    assert "held" in args
    assert '"label": "Go"' in "".join(a for a in args if isinstance(a, str))
    assert result.push_class == "discretionary"


async def test_create_delivered_stamps_delivered_at():
    conn = make_conn()
    conn.fetchrow = AsyncMock(return_value=_make_row())
    store, conn = make_store(conn)
    await store.create(
        event_type="e",
        source="s",
        title="t",
        body="b",
        target_type=None,
        target_id=None,
        push_class="accountability",
        urgency="normal",
        format="text",
        actions=[],
        delivery="delivered",
    )
    sql = conn.fetchrow.call_args.args[0]
    assert "CASE WHEN" in sql and "NOW()" in sql


async def test_list_held_orders_by_urgency_then_age():
    rows = [_make_row(delivery="held")]
    store, conn = make_store(make_conn(rows))

    held = await store.list_held()

    sql = conn.fetch.call_args.args[0]
    assert "delivery = 'held'" in sql
    assert "WHEN 'high' THEN 0" in sql and "created_at" in sql
    assert held[0].delivery == "held"


async def test_mark_released_and_failed_update_delivery():
    conn = make_conn(execute_result="UPDATE 1")
    store, _ = make_store(conn)
    nid = str(uuid4())

    await store.mark_released(nid)
    assert "delivery = 'released'" in conn.execute.call_args.args[0]
    await store.mark_failed(nid)
    assert "delivery = 'failed'" in conn.execute.call_args.args[0]


async def test_count_held():
    conn = make_conn()
    conn.fetchrow = AsyncMock(return_value=[3])
    store, conn = make_store(conn)
    assert await store.count_held() == 3
    assert "delivery = 'held'" in conn.fetchrow.call_args.args[0]


async def test_list_page_returns_push_class_and_delivery():
    rows = [_make_row(push_class="discretionary", delivery="suppressed")]
    store, conn = make_store(make_conn(rows))
    items, _ = await store.list_page()
    assert items[0].push_class == "discretionary"
    assert items[0].delivery == "suppressed"
    assert "push_class" in conn.fetch.call_args.args[0]
