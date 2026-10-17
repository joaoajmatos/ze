from datetime import datetime, timedelta

import pytest
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopState

from tests.pg._builders import make_loop, utcnow

pytestmark = pytest.mark.pg


async def test_set_confidence_stamps_prior_and_time(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.4)
    assert loop.confidence_prior is None and loop.confidence_changed_at is None

    await store.set_confidence(loop.id, 0.55)

    row = await store.get(loop.id)
    assert row.confidence == pytest.approx(0.55)
    assert row.confidence_prior == pytest.approx(0.4)
    assert abs((row.confidence_changed_at - utcnow()).total_seconds()) < 60


async def test_same_value_leaves_prior_and_time_alone(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.62)
    await store.set_confidence(loop.id, 0.62)
    row = await store.get(loop.id)
    assert row.confidence_prior is None and row.confidence_changed_at is None

    await store.set_confidence(loop.id, 0.5)
    first = await store.get(loop.id)
    await store.set_confidence(loop.id, 0.5)
    again = await store.get(loop.id)
    assert again.confidence_prior == pytest.approx(0.62)
    assert again.confidence_changed_at == first.confidence_changed_at


async def test_stamp_declared_stamps(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.35)
    await store.stamp_declared(
        loop.id, confidence=0.9, deadline=utcnow() + timedelta(days=7)
    )
    row = await store.get(loop.id)
    assert row.confidence_prior == pytest.approx(0.35)
    assert isinstance(row.confidence_changed_at, datetime)


async def test_promote_that_keeps_higher_confidence_stamps_nothing(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.8)
    await store.promote(loop.id, confidence=0.7, window_days=7)
    row = await store.get(loop.id)
    assert row.confidence == pytest.approx(0.8)
    assert row.confidence_prior is None and row.confidence_changed_at is None


async def test_promote_that_raises_stamps_prior(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.4)
    await store.promote(loop.id, confidence=0.7, window_days=7)
    row = await store.get(loop.id)
    assert row.confidence == pytest.approx(0.7)
    assert row.confidence_prior == pytest.approx(0.4)


async def test_list_returns_the_fields(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.4)
    await store.set_confidence(loop.id, 0.5)
    rows = await store.list([LoopState.SUSPECTED.value])
    assert rows[0].confidence_prior == pytest.approx(0.4)


async def test_promoted_through_corroboration_ends_at_point_seven_with_prior(pg_pool):
    from ze_worldstate.corroboration import PROMOTED_CONFIDENCE

    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.4)
    # The promote path of corroboration now writes confidence once, via promote().
    await store.promote(loop.id, confidence=PROMOTED_CONFIDENCE, window_days=7)
    row = await store.get(loop.id)
    assert row.state is LoopState.ACTIVE
    assert row.confidence == pytest.approx(0.7)
    assert row.confidence_prior == pytest.approx(0.4)
