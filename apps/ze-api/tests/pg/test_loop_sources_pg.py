from datetime import timedelta

import pytest
from ze_plugin.contribution import EvidenceRef
from ze_worldstate.lifecycle import Corroboration, LoopLifecycle
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopState, SourceKey

from tests.pg._builders import make_episode, make_loop, seed_source

pytestmark = pytest.mark.pg


async def _suspected(pool, title="Reply to Ana"):
    return await make_loop(
        pool, title=title, state=LoopState.SUSPECTED, confidence=0.3, confirmed_at=None
    )


async def test_source_rows_round_trip_through_the_store(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await _suspected(pg_pool)
    await seed_source(pg_pool, loop.id)

    [source] = await store.list_sources(loop.id)

    assert source.key == SourceKey("email", "T1")
    assert source.same_concern == 0.9
    assert source.model == "m" and source.latency_ms == 100


async def test_same_key_on_another_loop_is_allowed(pg_pool):
    a, b = await _suspected(pg_pool, "a"), await _suspected(pg_pool, "b")
    await seed_source(pg_pool, a.id)
    await seed_source(pg_pool, b.id)


async def test_deleting_the_loop_deletes_its_sources(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await _suspected(pg_pool)
    await seed_source(pg_pool, loop.id)
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM open_loops WHERE id = $1", loop.id)
    assert await store.list_sources(loop.id) == []


async def test_promoted_loop_past_its_deadline_is_a_drift_candidate(pg_pool):
    store = PostgresLoopStore(pg_pool)
    lifecycle = LoopLifecycle(pg_pool)
    loop = await _suspected(pg_pool)
    episode_id = await make_episode(pg_pool)
    promoted = await lifecycle.promote(
        loop.id,
        Corroboration(
            evidence=(EvidenceRef(kind="episode", id=episode_id),),
            entity_ids=(),
            key=SourceKey("email", "T1"),
            same_concern=0.9,
        ),
    )
    assert promoted.outcome == "promote"
    assert promoted.loop.drift_deadline - promoted.loop.confirmed_at == timedelta(days=7)
    assert await store.list_drift_candidates() == []

    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE open_loops SET drift_deadline = now() - interval '1 day' WHERE id = $1",
            loop.id,
        )
    assert [c.id for c in await store.list_drift_candidates()] == [loop.id]


async def test_list_sources_for_groups_by_loop(pg_pool):
    store = PostgresLoopStore(pg_pool)
    a = await _suspected(pg_pool, "a")
    b = await _suspected(pg_pool, "b")
    c = await _suspected(pg_pool, "c")
    await seed_source(pg_pool, a.id, "conversation", "c1", role="origin")
    await seed_source(pg_pool, a.id, "email", "T1")
    await seed_source(pg_pool, b.id, "calendar", "e1", role="origin")

    grouped = await store.list_sources_for([a.id, b.id, c.id])

    assert [s.key.inflow for s in grouped[a.id]] == ["conversation", "email"]
    assert [s.key.inflow for s in grouped[b.id]] == ["calendar"]
    assert c.id not in grouped
