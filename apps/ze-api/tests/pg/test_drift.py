from datetime import timedelta

import pytest
from ze_worldstate.jobs.drift_sweep import DriftSweepJob
from ze_worldstate.review import confirm_loop
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopState

from tests.pg._builders import make_loop, utcnow

pytestmark = pytest.mark.pg


async def _rewind(pool, loop_id, delta=timedelta(days=-1)):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE open_loops SET drift_deadline = now() + $2 WHERE id = $1",
            loop_id,
            delta,
        )


async def _state(store, loop_id):
    return (await store.get(loop_id)).state


async def test_declared_loop_past_deadline_is_candidate_and_drifts(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, deadline=utcnow() + timedelta(days=7))
    await _rewind(pg_pool, loop.id)

    assert [c.id for c in await store.list_drift_candidates()] == [loop.id]
    await DriftSweepJob(store).run()

    drifted = await store.get(loop.id)
    assert drifted.state is LoopState.DRIFTING
    assert "before the implied window elapsed" in drifted.drift_rationale


async def test_confirmed_suspected_loop_drifts(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confirmed_at=None)
    await confirm_loop(store, loop.id)
    await _rewind(pg_pool, loop.id)

    assert [c.id for c in await store.list_drift_candidates()] == [loop.id]
    await DriftSweepJob(store).run()
    assert await _state(store, loop.id) is LoopState.DRIFTING


async def test_future_deadline_is_not_a_candidate(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, deadline=utcnow() + timedelta(days=1))
    assert await store.list_drift_candidates() == []
    await DriftSweepJob(store).run()
    assert await _state(store, loop.id) is LoopState.ACTIVE


async def test_only_the_loop_past_its_deadline_drifts(pg_pool):
    store = PostgresLoopStore(pg_pool)
    late = await make_loop(pg_pool, title="late", deadline=utcnow() + timedelta(days=3))
    on_time = await make_loop(
        pg_pool, title="on time", deadline=utcnow() + timedelta(days=3)
    )
    await _rewind(pg_pool, late.id)
    await DriftSweepJob(store).run()
    assert await _state(store, late.id) is LoopState.DRIFTING
    assert await _state(store, on_time.id) is LoopState.ACTIVE


async def test_corroboration_moves_a_past_deadline_forward(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, deadline=utcnow() + timedelta(days=1))
    await _rewind(pg_pool, loop.id)

    await store.record_corroboration(loop.id)

    assert (await store.get(loop.id)).drift_deadline >= utcnow() + timedelta(
        days=7
    ) - timedelta(minutes=1)
    assert await store.list_drift_candidates() == []


async def test_corroboration_never_lowers_a_later_deadline(pg_pool):
    store = PostgresLoopStore(pg_pool)
    far = utcnow() + timedelta(days=30)
    loop = await make_loop(pg_pool, deadline=far)
    await store.record_corroboration(loop.id)
    assert (await store.get(loop.id)).drift_deadline == far


@pytest.mark.parametrize(
    "state", [LoopState.DRIFTING, LoopState.CLOSED, LoopState.SUSPECTED]
)
async def test_corroboration_ignores_loops_that_are_not_active(pg_pool, state):
    store = PostgresLoopStore(pg_pool)
    past = utcnow() - timedelta(days=2)
    loop = await make_loop(
        pg_pool,
        state=state,
        deadline=past,
        confirmed_at=None if state is LoopState.SUSPECTED else utcnow(),
    )
    before = await store.get(loop.id)
    await store.record_corroboration(loop.id)
    after = await store.get(loop.id)
    assert after.drift_deadline == before.drift_deadline and after.state is state


async def test_revived_loop_can_drift_again(pg_pool):
    if not hasattr(PostgresLoopStore, "stamp_declared"):
        pytest.skip("Phase 169 not on this branch")
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, deadline=utcnow() + timedelta(days=3))
    await _rewind(pg_pool, loop.id)
    await DriftSweepJob(store).run()
    assert await _state(store, loop.id) is LoopState.DRIFTING

    await store.transition(loop.id, "active", user_asked=True)
    await store.stamp_declared(
        loop.id, confidence=0.9, deadline=utcnow() - timedelta(days=1)
    )

    assert [c.id for c in await store.list_drift_candidates()] == [loop.id]
