from datetime import timedelta
from uuid import uuid4

import pytest
from ze_plugin.contribution import EvidenceRef
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopSource, LoopSourceRole, LoopState, SourceKey

from tests.pg._builders import make_loop

pytestmark = pytest.mark.pg


def _source(loop_id, inflow="email", ref="T1", role=LoopSourceRole.CORROBORATION, **kw):
    return LoopSource(
        loop_id=loop_id,
        role=role,
        key=SourceKey(inflow, ref),
        evidence=EvidenceRef(kind="episode", id=uuid4()),
        same_concern=None if role is LoopSourceRole.ORIGIN else 0.9,
        model="m",
        latency_ms=100,
        **kw,
    )


async def _suspected(pool, title="Reply to Ana"):
    return await make_loop(
        pool, title=title, state=LoopState.SUSPECTED, confidence=0.3, confirmed_at=None
    )


async def test_add_source_round_trips_and_duplicate_returns_none(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await _suspected(pg_pool)

    first = await store.add_source(_source(loop.id))
    assert first is not None and first.id is not None
    assert first.key == SourceKey("email", "T1")
    assert first.same_concern == 0.9
    assert await store.add_source(_source(loop.id)) is None
    assert len(await store.list_sources(loop.id)) == 1


async def test_same_key_on_another_loop_is_allowed(pg_pool):
    store = PostgresLoopStore(pg_pool)
    a, b = await _suspected(pg_pool, "a"), await _suspected(pg_pool, "b")
    assert await store.add_source(_source(a.id)) is not None
    assert await store.add_source(_source(b.id)) is not None


async def test_deleting_the_loop_deletes_its_sources(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await _suspected(pg_pool)
    await store.add_source(_source(loop.id))
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM open_loops WHERE id = $1", loop.id)
    assert await store.list_sources(loop.id) == []


async def test_promote_sets_active_confidence_and_deadline_once(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await _suspected(pg_pool)

    promoted = await store.promote(loop.id, confidence=0.7, window_days=7)

    assert promoted is not None
    assert promoted.state is LoopState.ACTIVE
    assert promoted.confidence == pytest.approx(0.7)
    assert promoted.drift_deadline - promoted.confirmed_at == timedelta(days=7)
    assert await store.promote(loop.id, confidence=0.7, window_days=7) is None


async def test_promote_keeps_a_higher_confidence(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(
        pg_pool, state=LoopState.SUSPECTED, confidence=0.8, confirmed_at=None
    )
    promoted = await store.promote(loop.id, confidence=0.7, window_days=7)
    assert promoted.confidence == pytest.approx(0.8)


async def test_promote_on_a_dropped_loop_returns_none(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await _suspected(pg_pool)
    await store.transition(loop.id, LoopState.DROPPED.value)
    assert await store.promote(loop.id, confidence=0.7, window_days=7) is None
    assert (await store.get(loop.id)).state is LoopState.DROPPED


async def test_promoted_loop_past_its_deadline_is_a_drift_candidate(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await _suspected(pg_pool)
    await store.promote(loop.id, confidence=0.7, window_days=7)
    assert await store.list_drift_candidates() == []

    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE open_loops SET drift_deadline = now() - interval '1 day' WHERE id = $1",
            loop.id,
        )
    assert [c.id for c in await store.list_drift_candidates()] == [loop.id]


async def test_mark_source_promoted(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await _suspected(pg_pool)
    row = await store.add_source(_source(loop.id))
    await store.mark_source_promoted(row.id)
    assert (await store.list_sources(loop.id))[0].promoted is True


async def test_list_sources_for_groups_by_loop(pg_pool):
    store = PostgresLoopStore(pg_pool)
    a = await _suspected(pg_pool, "a")
    b = await _suspected(pg_pool, "b")
    c = await _suspected(pg_pool, "c")
    await store.add_source(_source(a.id, "conversation", "c1", LoopSourceRole.ORIGIN))
    await store.add_source(_source(a.id, "email", "T1"))
    await store.add_source(_source(b.id, "calendar", "e1", LoopSourceRole.ORIGIN))

    grouped = await store.list_sources_for([a.id, b.id, c.id])

    assert [s.key.inflow for s in grouped[a.id]] == ["conversation", "email"]
    assert [s.key.inflow for s in grouped[b.id]] == ["calendar"]
    assert c.id not in grouped
