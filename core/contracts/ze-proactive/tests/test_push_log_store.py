from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from ze_proactive.push_log_store import ClaimResult, PushLogStore
from ze_proactive.types import OncePer

KEY = OncePer("loop:1", within=timedelta(days=7))


def _cm(value=None):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=value)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _store(fetchval=None, fetch=None):
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=fetchval)
    conn.fetch = AsyncMock(return_value=fetch or [])
    conn.transaction = MagicMock(return_value=_cm())
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_cm(conn))
    return PushLogStore(pool), conn


def _claim(store, discretionary=True, once_per=KEY, cap=5):
    return store.claim(
        event_type="e",
        once_per=once_per,
        discretionary=discretionary,
        max_discretionary=cap,
        payload="body",
    )


async def test_a_discretionary_claim_locks_the_key_then_the_budget_and_inserts():
    store, conn = _store(fetchval=[None, 2, 41])

    result = await _claim(store)

    assert result == ClaimResult("won", 41)
    locks = [c.args[0] for c in conn.execute.await_args_list]
    assert "push_log:key:" in locks[0]
    assert "push_log:budget" in locks[1]
    insert = conn.fetchval.await_args_list[-1].args
    assert "INSERT INTO push_log" in insert[0]
    assert insert[1:] == ("e", "loop:1", True, "body")


async def test_a_claim_inside_the_window_is_cooling_and_inserts_nothing():
    store, conn = _store(fetchval=[1])

    assert await _claim(store) == ClaimResult("cooling")
    assert conn.fetchval.await_count == 1
    cooling_args = conn.fetchval.await_args_list[0].args
    assert cooling_args[1:] == ("loop:1", timedelta(days=7))


async def test_a_claim_with_no_window_passes_none_so_it_cools_forever():
    store, conn = _store(fetchval=[1])

    await _claim(store, once_per=OncePer("insight:1"))

    assert conn.fetchval.await_args_list[0].args[2] is None


async def test_a_discretionary_claim_at_the_cap_is_over_budget_and_inserts_nothing():
    store, conn = _store(fetchval=[None, 5])

    assert await _claim(store, cap=5) == ClaimResult("over_budget")
    assert conn.fetchval.await_count == 2


async def test_an_accountability_claim_takes_no_budget_lock_and_skips_the_count():
    store, conn = _store(fetchval=[None, 9])

    result = await _claim(store, discretionary=False, cap=0)

    assert result == ClaimResult("won", 9)
    assert len(conn.execute.await_args_list) == 1
    assert conn.fetchval.await_count == 2


async def test_release_deletes_the_claim_by_id():
    store, conn = _store()

    await store.release(7)

    sql, claim_id = conn.execute.await_args.args
    assert "DELETE FROM push_log WHERE id" in sql
    assert claim_id == 7


async def test_is_cooling_reflects_the_cooldown_query():
    store, _ = _store(fetchval=[1])
    assert await store.is_cooling(KEY) is True
    store, _ = _store(fetchval=[None])
    assert await store.is_cooling(KEY) is False


async def test_window_sent_at_and_payloads_read_discretionary_rows_only():
    store, conn = _store(fetch=[{"sent_at": 1, "payload": "p"}])

    assert await store.window_sent_at(24.0) == [1]
    assert await store.recent_discretionary_payloads(48.0) == ["p"]
    for call in conn.fetch.await_args_list:
        assert "WHERE discretionary" in call.args[0]
