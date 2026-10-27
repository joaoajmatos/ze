from datetime import datetime

import pytest
from ze_plugin.contribution import EvidenceRef
from ze_worldstate.lifecycle import Corroboration, LoopLifecycle
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopState, SourceKey

from tests.pg._builders import make_episode, make_loop, utcnow

pytestmark = pytest.mark.pg


async def _corroborate(pool, loop_id, confidence, ref="T1"):
    episode_id = await make_episode(pool)
    return await LoopLifecycle(pool).corroborate(
        loop_id,
        Corroboration(
            evidence=(EvidenceRef(kind="episode", id=episode_id),),
            entity_ids=(),
            key=SourceKey("email", ref),
            same_concern=0.9,
            confidence=confidence,
        ),
    )


async def _promote(pool, loop_id):
    episode_id = await make_episode(pool)
    return await LoopLifecycle(pool).promote(
        loop_id,
        Corroboration(
            evidence=(EvidenceRef(kind="episode", id=episode_id),),
            entity_ids=(),
            key=SourceKey("email", "T1"),
            same_concern=0.9,
        ),
    )


async def test_a_confidence_change_stamps_prior_and_time(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.4)
    assert loop.confidence_prior is None and loop.confidence_changed_at is None

    await _corroborate(pg_pool, loop.id, 0.55)

    row = await store.get(loop.id)
    assert row.confidence == pytest.approx(0.55)
    assert row.confidence_prior == pytest.approx(0.4)
    assert abs((row.confidence_changed_at - utcnow()).total_seconds()) < 60


async def test_same_value_leaves_prior_and_time_alone(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.62)
    await _corroborate(pg_pool, loop.id, 0.62, ref="a")
    row = await store.get(loop.id)
    assert row.confidence_prior is None and row.confidence_changed_at is None

    await _corroborate(pg_pool, loop.id, 0.5, ref="b")
    first = await store.get(loop.id)
    await _corroborate(pg_pool, loop.id, 0.5, ref="c")
    again = await store.get(loop.id)
    assert again.confidence_prior == pytest.approx(0.62)
    assert again.confidence_changed_at == first.confidence_changed_at


async def test_confirm_stamps_the_prior(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.35)

    await LoopLifecycle(pg_pool).confirm(loop.id)

    row = await store.get(loop.id)
    assert row.confidence_prior == pytest.approx(0.35)
    assert isinstance(row.confidence_changed_at, datetime)


async def test_promote_that_keeps_higher_confidence_stamps_nothing(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.8)

    await _promote(pg_pool, loop.id)

    row = await store.get(loop.id)
    assert row.confidence == pytest.approx(0.8)
    assert row.confidence_prior is None and row.confidence_changed_at is None


async def test_promote_that_raises_stamps_prior(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.4)

    await _promote(pg_pool, loop.id)

    row = await store.get(loop.id)
    assert row.state is LoopState.ACTIVE
    assert row.confidence == pytest.approx(0.7)
    assert row.confidence_prior == pytest.approx(0.4)


async def test_list_returns_the_fields(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.4)
    await _corroborate(pg_pool, loop.id, 0.5)
    rows = await store.list([LoopState.SUSPECTED.value])
    assert rows[0].confidence_prior == pytest.approx(0.4)
