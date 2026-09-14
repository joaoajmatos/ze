from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import asyncpg

from ze_proactive.push_log_store import PushLogStore


def _make_conn(execute_side_effect=None):
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=execute_side_effect)
    return conn


def _make_pool(conn):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=cm)
    return pool


async def test_try_claim_first_call_returns_true_and_inserts():
    conn = _make_conn()
    store = PushLogStore(pool=_make_pool(conn))

    result = await store.try_claim("worldstate_loop_push", "loop-1", payload="drifting")

    assert result is True
    conn.execute.assert_awaited_once()
    sql = conn.execute.call_args[0][0]
    assert "INSERT INTO push_log" in sql
    assert "idempotency_key" in sql


async def test_try_claim_second_call_same_key_returns_false_no_raise():
    conn = _make_conn(
        execute_side_effect=asyncpg.UniqueViolationError("duplicate key")
    )
    store = PushLogStore(pool=_make_pool(conn))

    result = await store.try_claim("worldstate_loop_push", "loop-1", payload="drifting")

    assert result is False


async def test_try_claim_unaffected_by_plain_log_calls():
    """log() (idempotency_key=None-equivalent) is a distinct code path, untouched."""
    conn = _make_conn()
    store = PushLogStore(pool=_make_pool(conn))

    await store.log("workflow_failure:wf-1", payload="failed")

    conn.execute.assert_awaited_once()
    sql = conn.execute.call_args[0][0]
    assert "idempotency_key" not in sql


async def test_release_claim_deletes_row_allowing_reclaim():
    conn = _make_conn()
    store = PushLogStore(pool=_make_pool(conn))

    await store.release_claim("worldstate_loop_push", "loop-1")

    conn.execute.assert_awaited_once()
    sql, event_type, key = conn.execute.call_args[0]
    assert "DELETE FROM push_log" in sql
    assert event_type == "worldstate_loop_push"
    assert key == "loop-1"
