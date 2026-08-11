from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from ze_core.conversation.confirmations import PendingConfirmationStore


def _make_pool_mock(fetchrow=None, fetch=None, execute_result="DELETE 1"):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.fetch = AsyncMock(return_value=fetch or [])
    conn.execute = AsyncMock(return_value=execute_result)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncContextManagerMock(conn))
    return pool, conn


class _AsyncContextManagerMock:
    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *args):
        pass


def _make_row(thread_id="thread-1", request_id="req-1", prompt="Approve?"):
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "thread_id": thread_id,
        "request_id": request_id,
        "prompt": prompt,
        "actions": [{"label": "Approve", "value": "approve"}],
    }[key]
    return row


async def test_save_inserts_confirmation():
    pool, conn = _make_pool_mock()
    store = PendingConfirmationStore(pool=pool)
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)

    await store.save("thread-1", "req-1", "Approve?", [{"label": "Approve"}], expires)

    conn.execute.assert_called_once()
    sql = conn.execute.call_args[0][0]
    assert "INSERT INTO pending_confirmations" in sql
    assert "ON CONFLICT (request_id)" in sql


async def test_two_saves_same_thread_distinct_request_ids_both_persist():
    """Two save() calls on the same thread with distinct request_ids never clobber."""
    pool, conn = _make_pool_mock()
    store = PendingConfirmationStore(pool=pool)
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)

    await store.save("thread-1", "req-1", "Approve A?", [], expires)
    await store.save("thread-1", "req-2", "Approve B?", [], expires)

    assert conn.execute.call_count == 2
    first_call_args = conn.execute.call_args_list[0][0]
    second_call_args = conn.execute.call_args_list[1][0]
    assert first_call_args[2] == "req-1"
    assert second_call_args[2] == "req-2"


async def test_get_pending_for_thread_returns_list_with_both_rows():
    rows = [_make_row(request_id="req-1"), _make_row(request_id="req-2")]
    pool, conn = _make_pool_mock(fetch=rows)
    store = PendingConfirmationStore(pool=pool)

    result = await store.get_pending_for_thread("thread-1")

    assert isinstance(result, list)
    assert len(result) == 2
    assert {row["request_id"] for row in result} == {"req-1", "req-2"}


async def test_get_pending_for_thread_returns_empty_list_when_none():
    pool, conn = _make_pool_mock(fetch=[])
    store = PendingConfirmationStore(pool=pool)

    result = await store.get_pending_for_thread("thread-1")

    assert result == []


async def test_get_pending_returns_single_row_by_request_id():
    row = _make_row(request_id="req-1")
    pool, conn = _make_pool_mock(fetchrow=row)
    store = PendingConfirmationStore(pool=pool)

    result = await store.get_pending("req-1")

    assert result is not None
    assert result["request_id"] == "req-1"
    assert result["prompt"] == "Approve?"


async def test_get_pending_returns_none_when_missing():
    pool, conn = _make_pool_mock(fetchrow=None)
    store = PendingConfirmationStore(pool=pool)

    result = await store.get_pending("req-missing")

    assert result is None


async def test_clear_deletes_only_matching_row():
    pool, conn = _make_pool_mock(execute_result="DELETE 1")
    store = PendingConfirmationStore(pool=pool)

    deleted = await store.clear("thread-1", "req-1")

    assert deleted is True
    conn.execute.assert_called_once()
    sql, thread_arg, request_arg = conn.execute.call_args[0]
    assert "WHERE thread_id = $1 AND request_id = $2" in sql
    assert thread_arg == "thread-1"
    assert request_arg == "req-1"


async def test_clear_returns_false_when_missing():
    pool, conn = _make_pool_mock(execute_result="DELETE 0")
    store = PendingConfirmationStore(pool=pool)

    deleted = await store.clear("thread-1", "req-1")

    assert deleted is False


async def test_clear_leaves_other_request_ids_untouched():
    """clear() for one request_id must not affect another gate's row."""
    pool, conn = _make_pool_mock(execute_result="DELETE 1")
    store = PendingConfirmationStore(pool=pool)

    await store.clear("thread-1", "req-1")

    _, thread_arg, request_arg = conn.execute.call_args[0]
    assert request_arg == "req-1"
    assert request_arg != "req-2"
