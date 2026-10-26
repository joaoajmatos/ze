import asyncio
from datetime import timedelta

import pytest
from ze_proactive.push_log_store import PushLogStore
from ze_proactive.types import OncePer

pytestmark = pytest.mark.pg

WEEK = timedelta(days=7)


async def _claim(store, key, *, within=None, discretionary=True, cap=5, payload=None):
    return await store.claim(
        event_type="e",
        once_per=OncePer(key, within=within),
        discretionary=discretionary,
        max_discretionary=cap,
        payload=payload,
    )


async def _age(pool, hours):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE push_log SET sent_at = now() - make_interval(hours => $1)", hours
        )


async def test_a_second_claim_inside_the_window_is_cooling(pg_pool):
    store = PushLogStore(pg_pool)
    assert (await _claim(store, "loop:1", within=WEEK)).status == "won"
    assert (await _claim(store, "loop:1", within=WEEK)).status == "cooling"
    assert await store.is_cooling(OncePer("loop:1", within=WEEK)) is True


async def test_a_claim_older_than_the_window_no_longer_cools(pg_pool):
    store = PushLogStore(pg_pool)
    await _claim(store, "loop:1", within=WEEK)
    await _age(pg_pool, 24 * 8)

    assert await store.is_cooling(OncePer("loop:1", within=WEEK)) is False
    assert (await _claim(store, "loop:1", within=WEEK)).status == "won"


async def test_no_window_cools_forever(pg_pool):
    store = PushLogStore(pg_pool)
    await _claim(store, "insight:1")
    await _age(pg_pool, 24 * 400)

    assert (await _claim(store, "insight:1")).status == "cooling"


async def test_the_daily_cap_returns_over_budget_and_inserts_nothing(pg_pool):
    store = PushLogStore(pg_pool)
    for i in range(2):
        assert (await _claim(store, f"k{i}", cap=2)).status == "won"

    assert (await _claim(store, "k2", cap=2)).status == "over_budget"
    assert len(await store.window_sent_at(24.0)) == 2
    assert await store.is_cooling(OncePer("k2")) is False


async def test_accountability_claims_do_not_count_against_the_budget(pg_pool):
    store = PushLogStore(pg_pool)
    for i in range(3):
        assert (
            await _claim(store, f"acc{i}", discretionary=False, cap=1)
        ).status == "won"

    assert await store.window_sent_at(24.0) == []
    assert (await _claim(store, "d", cap=1)).status == "won"


async def test_release_frees_the_key(pg_pool):
    store = PushLogStore(pg_pool)
    won = await _claim(store, "loop:1", within=WEEK)
    await store.release(won.claim_id)

    assert (await _claim(store, "loop:1", within=WEEK)).status == "won"


async def test_two_concurrent_claims_on_one_key_give_one_winner(pg_pool):
    store = PushLogStore(pg_pool)
    results = await asyncio.gather(
        _claim(store, "loop:1", within=WEEK), _claim(store, "loop:1", within=WEEK)
    )

    assert sorted(r.status for r in results) == ["cooling", "won"]


async def test_concurrent_claims_on_different_keys_do_not_overrun_the_cap(pg_pool):
    store = PushLogStore(pg_pool)
    results = await asyncio.gather(*(_claim(store, f"k{i}", cap=2) for i in range(4)))

    assert sorted(r.status for r in results) == ["over_budget"] * 2 + ["won"] * 2


async def test_claims_of_two_keys_inside_one_window_both_win(pg_pool):
    store = PushLogStore(pg_pool)
    assert (await _claim(store, "loop:1", within=WEEK)).status == "won"
    assert (await _claim(store, "loop:2", within=WEEK)).status == "won"


async def test_recent_discretionary_payloads_are_discretionary_in_window_newest_first(
    pg_pool,
):
    store = PushLogStore(pg_pool)
    await _claim(store, "old", payload="old body")
    await _age(pg_pool, 60)
    await _claim(store, "a", payload="first")
    await _claim(store, "b", payload="second")
    await _claim(store, "acc", discretionary=False, payload="acc body")
    await _claim(store, "nobody")

    assert await store.recent_discretionary_payloads(48.0) == ["second", "first"]
