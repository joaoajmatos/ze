"""199 US3: a loop's claim kind follows its state; the stored column is gone."""

import pytest
from ze_agents.claims import ClaimKind
from ze_automation.goals.postgres import PostgresGoalStore
from ze_correlation.store import PostgresHypothesisStore
from ze_plugin.contribution import EvidenceRef
from ze_priority.view import PriorityView
from ze_worldstate.lifecycle import Corroboration, LoopLifecycle
from ze_worldstate.rest import list_loops
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopState, SourceKey

from tests.pg._builders import link_evidence, make_episode, make_loop

pytestmark = pytest.mark.pg


async def _suspected(pool, title: str = "Renew the passport"):
    return await make_loop(
        pool, title=title, state=LoopState.SUSPECTED, confidence=0.4, confirmed_at=None
    )


async def test_new_suspected_loop_is_a_suspicion(pg_pool):
    store = PostgresLoopStore(pg_pool)
    created = await _suspected(pg_pool)

    assert created.claim_kind is ClaimKind.SUSPICION
    assert (await store.get(created.id)).claim_kind is ClaimKind.SUSPICION


async def test_confirmed_loop_is_a_priority(pg_pool):
    store, lifecycle = PostgresLoopStore(pg_pool), LoopLifecycle(pg_pool)
    created = await _suspected(pg_pool)

    confirmed = await lifecycle.confirm(created.id)

    assert confirmed.claim_kind is ClaimKind.PRIORITY
    assert (await store.get(created.id)).claim_kind is ClaimKind.PRIORITY


async def test_promoted_loop_is_a_priority(pg_pool):
    store, lifecycle = PostgresLoopStore(pg_pool), LoopLifecycle(pg_pool)
    created = await _suspected(pg_pool)
    episode_id = await make_episode(pg_pool)

    promoted = await lifecycle.promote(
        created.id,
        Corroboration(
            evidence=(EvidenceRef(kind="episode", id=episode_id),),
            entity_ids=(),
            key=SourceKey("email", "T1"),
            same_concern=0.9,
        ),
    )

    assert promoted.loop.claim_kind is ClaimKind.PRIORITY
    assert (await store.get(created.id)).claim_kind is ClaimKind.PRIORITY


async def test_drifting_and_closed_loops_stay_priorities(pg_pool):
    store, lifecycle = PostgresLoopStore(pg_pool), LoopLifecycle(pg_pool)
    created = await _suspected(pg_pool)
    await lifecycle.confirm(created.id)
    evidence = await link_evidence(pg_pool, created.id, kind="fact")

    [drifting] = await lifecycle.decay_from_evidence("fact", evidence)
    assert drifting.state is LoopState.DRIFTING
    assert drifting.claim_kind is ClaimKind.PRIORITY
    assert (await store.get(created.id)).claim_kind is ClaimKind.PRIORITY

    closed = await lifecycle.close(created.id)
    assert closed.claim_kind is ClaimKind.PRIORITY
    assert (await store.get(created.id)).claim_kind is ClaimKind.PRIORITY


async def test_dropped_loop_has_no_claim_kind_and_rest_says_null(pg_pool):
    store, lifecycle = PostgresLoopStore(pg_pool), LoopLifecycle(pg_pool)
    created = await _suspected(pg_pool)

    await lifecycle.drop(created.id)

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
    store, lifecycle = PostgresLoopStore(pg_pool), LoopLifecycle(pg_pool)
    created = await _suspected(pg_pool)
    await lifecycle.confirm(created.id)
    view = PriorityView(
        store, PostgresGoalStore(pg_pool), PostgresHypothesisStore(pg_pool)
    )

    ranking = await view.rank()

    [item] = [i for i in ranking.items if i.source_kind == "loop"]
    assert item.claim_kind is ClaimKind.PRIORITY
