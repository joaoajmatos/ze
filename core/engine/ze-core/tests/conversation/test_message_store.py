from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_core.conversation.messages import Message, PostgresMessageStore


def _make_message(**kwargs) -> Message:
    return Message(
        id=kwargs.get("id", uuid4()),
        role=kwargs.get("role", "assistant"),
        text=kwargs.get("text", "Hello"),
        components=kwargs.get("components", []),
        read=kwargs.get("read", False),
        created_at=kwargs.get("created_at", datetime.now(timezone.utc)),
        thread_id=kwargs.get("thread_id", None),
        replaces=kwargs.get("replaces", None),
        replaced_by=kwargs.get("replaced_by", None),
    )


def _make_pool_mock(rows=None, execute_side_effect=None):
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows or [])
    conn.fetchrow = AsyncMock(return_value=rows[0] if rows else None)
    conn.execute = AsyncMock(side_effect=execute_side_effect)

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


def _make_row(msg: Message, rollback=None):
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": msg.id,
        "role": msg.role,
        "text": msg.text,
        "components": json.dumps(msg.components),
        "read": msg.read,
        "thread_id": msg.thread_id,
        "created_at": msg.created_at,
        "replaces": msg.replaces,
        "replaced_by": msg.replaced_by,
        "rollback": rollback,
    }[key]
    return row


async def test_get_traces_returns_map():
    msg_id = uuid4()
    trace_data = {
        "agent": "companion",
        "routing_method": "embedding",
        "confidence": 0.9,
        "score_gap": 0.1,
        "is_compound": False,
        "subtasks": [],
        "memory_chunks": [],
        "tool_calls": [],
        "total_duration_ms": 50,
    }
    row = MagicMock()
    row.__getitem__ = lambda self, key: {"id": msg_id, "trace": trace_data}[key]

    pool, conn = _make_pool_mock(rows=[row])
    store = PostgresMessageStore(pool=pool)

    result = await store.get_traces([msg_id])

    assert msg_id in result
    assert result[msg_id].agent == "companion"
    sql = conn.fetch.call_args[0][0]
    assert "ANY($1::uuid[])" in sql


async def test_get_traces_empty_list():
    pool, conn = _make_pool_mock()
    store = PostgresMessageStore(pool=pool)
    result = await store.get_traces([])
    assert result == {}
    conn.fetch.assert_not_called()


async def test_save_writes_correct_row():
    pool, conn = _make_pool_mock()
    store = PostgresMessageStore(pool=pool)
    msg = _make_message(text="Hello", role="assistant")

    await store.save(msg)

    conn.execute.assert_called_once()
    call_args = conn.execute.call_args[0]
    assert msg.id in call_args
    assert "assistant" in call_args
    assert "Hello" in call_args


async def test_list_since_returns_ascending_order():
    msg1 = _make_message(id=uuid4())
    msg2 = _make_message(id=uuid4())
    pool, conn = _make_pool_mock(rows=[_make_row(msg1), _make_row(msg2)])
    store = PostgresMessageStore(pool=pool)

    since = datetime(2020, 1, 1, tzinfo=timezone.utc)
    results = await store.list_since(since, limit=10)

    assert len(results) == 2
    conn.fetch.assert_called_once()
    _, limit_arg = conn.fetch.call_args[0][1], conn.fetch.call_args[0][2]
    assert limit_arg == 10


async def test_mark_read_flips_read_flag():
    pool, conn = _make_pool_mock()
    store = PostgresMessageStore(pool=pool)
    ids = [uuid4(), uuid4()]

    await store.mark_read(ids)

    conn.execute.assert_called_once()
    sql = conn.execute.call_args[0][0]
    assert "read = TRUE" in sql


async def test_mark_read_noop_for_empty_list():
    pool, conn = _make_pool_mock()
    store = PostgresMessageStore(pool=pool)

    await store.mark_read([])

    conn.execute.assert_not_called()


async def test_list_unread_excludes_read_messages():
    msg = _make_message(read=False)
    pool, conn = _make_pool_mock(rows=[_make_row(msg)])
    store = PostgresMessageStore(pool=pool)

    results = await store.list_unread()

    assert len(results) == 1
    sql = conn.fetch.call_args[0][0]
    assert "NOT read" in sql


async def test_save_persists_replaces_link():
    pool, conn = _make_pool_mock()
    old_id = uuid4()
    await PostgresMessageStore(pool=pool).save(_make_message(replaces=old_id))
    args = conn.execute.call_args[0]
    assert old_id in args
    assert "replaces" in args[0]


async def test_list_by_thread_hides_superseded_by_default():
    pool, conn = _make_pool_mock(rows=[])
    store = PostgresMessageStore(pool=pool)
    await store.list_by_thread("t1")
    sql, *params = conn.fetch.call_args[0]
    assert "replaced_by IS NULL" in sql
    assert params[-1] is False
    await store.list_by_thread("t1", include_superseded=True)
    assert conn.fetch.call_args[0][-1] is True


async def test_list_since_and_unread_hide_superseded_by_default():
    pool, conn = _make_pool_mock(rows=[])
    store = PostgresMessageStore(pool=pool)
    await store.list_since(datetime(2020, 1, 1, tzinfo=timezone.utc))
    assert "replaced_by IS NULL" in conn.fetch.call_args[0][0]
    assert conn.fetch.call_args[0][-1] is False
    await store.list_unread("t1")
    assert "replaced_by IS NULL" in conn.fetch.call_args[0][0]
    await store.list_unread()
    assert "replaced_by IS NULL" in conn.fetch.call_args[0][0]


async def test_get_message_roundtrips_supersession_fields():
    new_id = uuid4()
    msg = _make_message(replaced_by=new_id)
    pool, _ = _make_pool_mock(rows=[_make_row(msg)])
    got = await PostgresMessageStore(pool=pool).get_message(msg.id)
    assert got is not None
    assert got.replaced_by == new_id


async def test_get_message_missing_returns_none():
    pool, _ = _make_pool_mock()
    assert await PostgresMessageStore(pool=pool).get_message(uuid4()) is None


async def test_latest_assistant_id_skips_superseded():
    mid = uuid4()
    row = MagicMock()
    row.__getitem__ = lambda self, key: {"id": mid}[key]
    pool, conn = _make_pool_mock(rows=[row])
    assert await PostgresMessageStore(pool=pool).latest_assistant_id("t1") == mid
    sql = conn.fetchrow.call_args[0][0]
    assert "role = 'assistant'" in sql
    assert "replaced_by IS NULL" in sql
    assert "ORDER BY created_at DESC" in sql


async def test_latest_assistant_id_none_for_empty_thread():
    pool, _ = _make_pool_mock()
    assert await PostgresMessageStore(pool=pool).latest_assistant_id("t1") is None


async def test_mark_superseded_requires_replacement_to_exist():
    pool, conn = _make_pool_mock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    old, new = uuid4(), uuid4()
    assert await PostgresMessageStore(pool=pool).mark_superseded(old, new) is True
    sql = conn.execute.call_args[0][0]
    assert "replaced_by IS NULL" in sql
    assert "EXISTS (SELECT 1 FROM messages WHERE id = $2)" in sql
    assert conn.execute.call_args[0][1:] == (old, new)


async def test_mark_superseded_false_when_nothing_updated():
    pool, conn = _make_pool_mock()
    conn.execute = AsyncMock(return_value="UPDATE 0")
    assert (
        await PostgresMessageStore(pool=pool).mark_superseded(uuid4(), uuid4()) is False
    )


async def test_get_messages_returns_map_and_skips_empty_query():
    msg = _make_message()
    pool, conn = _make_pool_mock(rows=[_make_row(msg)])
    store = PostgresMessageStore(pool=pool)
    got = await store.get_messages([msg.id])
    assert got[msg.id].text == "Hello"
    assert "ANY($1::uuid[])" in conn.fetch.call_args[0][0]
    conn.fetch.reset_mock()
    assert await store.get_messages([]) == {}
    conn.fetch.assert_not_called()


async def test_previous_user_message_joins_same_thread_before_reply():
    user = _make_message(role="user", text="question")
    pool, conn = _make_pool_mock(rows=[_make_row(user)])
    got = await PostgresMessageStore(pool=pool).previous_user_message(uuid4())
    assert got.text == "question"
    sql = conn.fetchrow.call_args[0][0]
    assert "u.role = 'user'" in sql
    assert "u.created_at < a.created_at" in sql
    assert "ORDER BY u.created_at DESC" in sql


async def test_get_message_loads_rollback_record():
    from ze_core.conversation.messages.types import RollbackEntry, RollbackRecord

    msg = _make_message()
    record = RollbackRecord(
        state="rolled_back_retry_failed",
        entries=[
            RollbackEntry(
                entry_id="e1",
                call_index=0,
                tool="set_reminder",
                undo_tool="cancel_reminder",
                effect_phrase="set a reminder",
                outcome="undone",
                at="t",
            )
        ],
        started_at="t",
        updated_at="t",
    )
    from dataclasses import asdict

    row = _make_row(msg, rollback=asdict(record))
    pool, _ = _make_pool_mock(rows=[row])
    loaded = await PostgresMessageStore(pool=pool).get_message(msg.id)
    assert loaded is not None and loaded.rollback == record


async def test_message_without_rollback_loads_none():
    msg = _make_message()
    pool, _ = _make_pool_mock(rows=[_make_row(msg)])
    loaded = await PostgresMessageStore(pool=pool).get_message(msg.id)
    assert loaded is not None and loaded.rollback is None


async def test_rollback_column_is_selected_on_every_read():
    msg = _make_message()
    pool, conn = _make_pool_mock(rows=[_make_row(msg)])
    store = PostgresMessageStore(pool=pool)
    await store.list_since(datetime.now(timezone.utc))
    await store.list_by_thread("t")
    await store.list_unread("t")
    await store.list_unread()
    await store.get_message(msg.id)
    await store.get_messages([msg.id])
    await store.previous_user_message(msg.id)
    sqls = [c.args[0] for c in conn.fetch.call_args_list + conn.fetchrow.call_args_list]
    assert len(sqls) == 7
    assert all("rollback" in sql for sql in sqls)


async def test_set_rollback_overwrites_with_jsonb():
    from dataclasses import asdict

    from ze_core.conversation.messages.types import RollbackRecord

    pool, conn = _make_pool_mock()
    record = RollbackRecord(state="partial", entries=[], started_at="t", updated_at="u")
    mid = uuid4()
    await PostgresMessageStore(pool=pool).set_rollback(mid, record)
    sql, payload, target = conn.execute.call_args.args
    assert "UPDATE messages SET rollback = $1::jsonb WHERE id = $2" in sql
    assert payload == asdict(record)
    assert target == mid


async def test_unreadable_rollback_record_loads_as_none():
    msg = _make_message()
    pool, _ = _make_pool_mock(rows=[_make_row(msg, rollback={"entries": "bad"})])
    loaded = await PostgresMessageStore(pool=pool).get_message(msg.id)
    assert loaded is not None and loaded.rollback is None
