from uuid import uuid4

import pytest
from ze_worldstate.lifecycle import LoopLifecycle
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopState

from tests.pg._builders import make_loop

pytestmark = pytest.mark.pg


@pytest.mark.parametrize(
    "state", [LoopState.SUSPECTED, LoopState.ACTIVE, LoopState.DRIFTING]
)
async def test_link_sets_reminder_then_goal_without_overwriting(pg_pool, state):
    store, lifecycle = PostgresLoopStore(pg_pool), LoopLifecycle(pg_pool)
    loop = await make_loop(pg_pool, state=state)
    first, second = uuid4(), uuid4()

    assert await lifecycle.link(loop.id, reminder_id=first) is True
    assert await lifecycle.link(loop.id, reminder_id=second) is False
    got = await store.get(loop.id)
    assert got.reminder_id == first and got.goal_id is None


async def test_link_goal_does_not_touch_reminder(pg_pool):
    store, lifecycle = PostgresLoopStore(pg_pool), LoopLifecycle(pg_pool)
    loop = await make_loop(pg_pool)
    reminder_id = uuid4()
    await lifecycle.link(loop.id, reminder_id=reminder_id)
    async with pg_pool.acquire() as conn:
        goal_id = await conn.fetchval(
            "INSERT INTO goals (title, objective, success_condition, status)"
            " VALUES ('g', 'o', 's', 'active') RETURNING id"
        )
    assert await lifecycle.link(loop.id, goal_id=goal_id) is True
    got = await store.get(loop.id)
    assert (got.reminder_id, got.goal_id) == (reminder_id, goal_id)


@pytest.mark.parametrize("state", [LoopState.CLOSED, LoopState.DROPPED])
async def test_terminal_loop_is_never_linked(pg_pool, state):
    store, lifecycle = PostgresLoopStore(pg_pool), LoopLifecycle(pg_pool)
    loop = await make_loop(pg_pool, state=state)
    assert await lifecycle.link(loop.id, reminder_id=uuid4()) is False
    assert (await store.get(loop.id)).reminder_id is None


async def test_unknown_loop_returns_false(pg_pool):
    assert await LoopLifecycle(pg_pool).link(uuid4(), reminder_id=uuid4()) is False
