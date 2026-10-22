"""199 US3: a loop's claim kind follows its state; the stored column is gone."""

import pytest
from ze_agents.claims import ClaimKind
from ze_priority.view import PriorityView
from ze_automation.goals.postgres import PostgresGoalStore
from ze_correlation.store import PostgresHypothesisStore
from ze_worldstate import review
from ze_worldstate.rest import list_loops
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopProvenance, LoopState, OpenLoop

pytestmark = pytest.mark.pg


def _suspected(title: str = "Renew the passport") -> OpenLoop:
    return OpenLoop(
        title=title,
        provenance=LoopProvenance.CONVERSATION,
        confidence=0.4,
        state=LoopState.SUSPECTED,
    )


async def test_new_suspected_loop_is_a_suspicion(pg_pool):
    store = PostgresLoopStore(pg_pool)

    created = await store.create(_suspected())

    assert created.claim_kind is ClaimKind.SUSPICION
    assert (await store.get(created.id)).claim_kind is ClaimKind.SUSPICION


async def test_confirmed_loop_is_a_priority(pg_pool):
    store = PostgresLoopStore(pg_pool)
    created = await store.create(_suspected())

    await review.confirm_loop(store, created.id)

    assert (await store.get(created.id)).claim_kind is ClaimKind.PRIORITY


async def test_promoted_loop_is_a_priority(pg_pool):
    store = PostgresLoopStore(pg_pool)
    created = await store.create(_suspected())

    promoted = await store.promote(created.id, confidence=0.7, window_days=7)

    assert promoted.claim_kind is ClaimKind.PRIORITY
    assert (await store.get(created.id)).claim_kind is ClaimKind.PRIORITY


async def test_drifting_and_closed_loops_stay_priorities(pg_pool):
    store = PostgresLoopStore(pg_pool)
    created = await store.create(_suspected())
    await review.confirm_loop(store, created.id)

    drifting = await store.transition(created.id, "drifting")
    assert drifting.claim_kind is ClaimKind.PRIORITY
    assert (await store.get(created.id)).claim_kind is ClaimKind.PRIORITY

    closed = await store.transition(created.id, "closed")
    assert closed.claim_kind is ClaimKind.PRIORITY
    assert (await store.get(created.id)).claim_kind is ClaimKind.PRIORITY


async def test_dropped_loop_has_no_claim_kind_and_rest_says_null(pg_pool):
    store = PostgresLoopStore(pg_pool)
    created = await store.create(_suspected())

    await review.drop_loop(store, created.id)

    assert (await store.get(created.id)).claim_kind is None
    [item] = await list_loops(store, ["dropped"])
    assert item["claim_kind"] is None


async def test_open_loops_has_no_claim_kind_column(pg_pool):
    async with pg_pool.acquire() as conn:
        found = await conn.fetchval(
            """
            SELECT count(*) FROM information_schema.columns
            WHERE table_name = 'open_loops' AND column_name = 'claim_kind'
            """
        )
    assert found == 0


async def test_priority_view_returns_a_confirmed_loop_as_priority(pg_pool):
    store = PostgresLoopStore(pg_pool)
    created = await store.create(_suspected())
    await review.confirm_loop(store, created.id)
    view = PriorityView(
        store, PostgresGoalStore(pg_pool), PostgresHypothesisStore(pg_pool)
    )

    ranking = await view.rank()

    [item] = [i for i in ranking.items if i.source_kind == "loop"]
    assert item.claim_kind is ClaimKind.PRIORITY
