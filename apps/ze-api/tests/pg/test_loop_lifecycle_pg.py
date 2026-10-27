"""Every lifecycle event against a real Postgres (spec FR-012, SC-001, SC-004).

US1 part: confirm, close, drop, expire, decay and drift each write atomically.
"""

import asyncio
from datetime import timedelta
from uuid import uuid4

import asyncpg
import pytest
from ze_agents.claims import DecayProfile, decay
from ze_plugin.contribution import EvidenceRef
from ze_worldstate.errors import InvalidLoopTransitionError, LoopNotFoundError
from ze_worldstate.fingerprint import compute_evidence_fingerprint
from ze_worldstate.lifecycle import LoopLifecycle
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopState

from tests.pg._builders import fail_writes_to, link_evidence, make_loop, utcnow

pytestmark = pytest.mark.pg


def _decayed(confidence: float, *, remaining: int, total: int) -> float:
    return decay(
        confidence,
        DecayProfile.EVIDENCE_WEIGHTED,
        remaining_evidence=remaining,
        total_evidence=total,
    )


@pytest.fixture
def lifecycle(pg_pool) -> LoopLifecycle:
    return LoopLifecycle(pg_pool)


@pytest.fixture
def store(pg_pool) -> PostgresLoopStore:
    return PostgresLoopStore(pg_pool)


# ── confirm ───────────────────────────────────────────────────────────────────


async def test_confirm_stamps_every_field_and_returns_the_stored_row(
    pg_pool, lifecycle, store
):
    loop = await make_loop(
        pg_pool, state=LoopState.SUSPECTED, provenance="email", confidence=0.35,
        confirmed_at=None, rationale="old",
    )

    returned = await lifecycle.confirm(loop.id)

    stored = await store.get(loop.id)
    assert returned == stored
    assert stored.updated_at > loop.updated_at
    assert stored.state is LoopState.ACTIVE
    assert stored.confidence == pytest.approx(0.9, abs=1e-6)
    assert stored.confidence_prior == pytest.approx(0.35, abs=1e-6)
    assert stored.confirmed_at is not None
    assert stored.drift_rationale is None
    assert abs((stored.drift_deadline - (utcnow() + timedelta(days=7))).total_seconds()) < 60
    assert stored.provenance == "email"


async def test_confirm_refuses_every_state_but_suspected(pg_pool, lifecycle):
    for state in (LoopState.ACTIVE, LoopState.DRIFTING, LoopState.CLOSED, LoopState.DROPPED):
        loop = await make_loop(pg_pool, state=state)
        with pytest.raises(InvalidLoopTransitionError):
            await lifecycle.confirm(loop.id)


async def test_confirm_on_a_missing_loop_raises_not_found(lifecycle):
    with pytest.raises(LoopNotFoundError):
        await lifecycle.confirm(uuid4())


# ── close ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("state", [LoopState.ACTIVE, LoopState.DRIFTING])
async def test_close_moves_a_live_loop_and_stamps_closed_at(pg_pool, lifecycle, state):
    loop = await make_loop(pg_pool, state=state)
    closed = await lifecycle.close(loop.id)
    assert closed.state is LoopState.CLOSED
    assert closed.closed_at is not None


async def test_close_is_refused_from_suspected(pg_pool, lifecycle, store):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    with pytest.raises(InvalidLoopTransitionError):
        await lifecycle.close(loop.id)
    assert (await store.get(loop.id)).state is LoopState.SUSPECTED


# ── drop ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "state", [LoopState.SUSPECTED, LoopState.ACTIVE, LoopState.DRIFTING]
)
async def test_drop_writes_state_closed_at_and_fingerprint_together(
    pg_pool, lifecycle, store, state
):
    loop = await make_loop(pg_pool, state=state, confidence=0.4)
    evidence = await link_evidence(pg_pool, loop.id)

    dropped = await lifecycle.drop(loop.id)

    stored = await store.get(loop.id)
    assert dropped == stored
    assert stored.state is LoopState.DROPPED
    assert stored.closed_at is not None
    assert stored.dismissed_evidence_fingerprint == compute_evidence_fingerprint(
        [EvidenceRef(kind="episode", id=evidence)]
    )


async def test_drop_with_no_evidence_writes_the_fingerprint_of_nothing(
    pg_pool, lifecycle
):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    dropped = await lifecycle.drop(loop.id)
    assert dropped.dismissed_evidence_fingerprint == compute_evidence_fingerprint([])


async def test_drop_with_the_row_write_failing_changes_nothing(
    pg_pool, lifecycle, store
):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    await link_evidence(pg_pool, loop.id)
    await fail_writes_to(pg_pool, "open_loops")

    with pytest.raises(asyncpg.PostgresError):
        await lifecycle.drop(loop.id)

    stored = await store.get(loop.id)
    assert stored.state is LoopState.SUSPECTED
    assert stored.dismissed_evidence_fingerprint is None
    assert stored.closed_at is None


async def test_drop_reads_evidence_even_when_link_writes_would_fail(
    pg_pool, lifecycle, store
):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    evidence = await link_evidence(pg_pool, loop.id)
    await fail_writes_to(pg_pool, "memory_relationships")

    dropped = await lifecycle.drop(loop.id)

    assert dropped.dismissed_evidence_fingerprint == compute_evidence_fingerprint(
        [EvidenceRef(kind="episode", id=evidence)]
    )


@pytest.mark.parametrize("state", [LoopState.CLOSED, LoopState.DROPPED])
async def test_drop_is_refused_on_a_terminal_loop(pg_pool, lifecycle, state):
    loop = await make_loop(pg_pool, state=state)
    with pytest.raises(InvalidLoopTransitionError):
        await lifecycle.drop(loop.id)


# ── expire ────────────────────────────────────────────────────────────────────


async def test_expire_drops_a_suspected_loop_with_its_fingerprint(
    pg_pool, lifecycle, store
):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    evidence = await link_evidence(pg_pool, loop.id)

    expired = await lifecycle.expire(loop.id)

    assert expired.state is LoopState.DROPPED
    assert expired.dismissed_evidence_fingerprint == compute_evidence_fingerprint(
        [EvidenceRef(kind="episode", id=evidence)]
    )
    assert (await store.get(loop.id)) == expired


async def test_expire_with_no_evidence_writes_a_null_fingerprint(pg_pool, lifecycle):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    expired = await lifecycle.expire(loop.id)
    assert expired.state is LoopState.DROPPED
    assert expired.dismissed_evidence_fingerprint is None


@pytest.mark.parametrize(
    "state",
    [LoopState.ACTIVE, LoopState.DRIFTING, LoopState.CLOSED, LoopState.DROPPED],
)
async def test_expire_leaves_any_other_state_alone(pg_pool, lifecycle, store, state):
    loop = await make_loop(pg_pool, state=state)
    assert await lifecycle.expire(loop.id) is None
    assert (await store.get(loop.id)).state is state


# ── decay ─────────────────────────────────────────────────────────────────────


async def test_decay_lowers_confidence_and_drifts_an_active_loop_in_one_write(
    pg_pool, lifecycle, store
):
    loop = await make_loop(pg_pool, state=LoopState.ACTIVE, confidence=0.9)
    evidence = await link_evidence(pg_pool, loop.id, kind="fact")

    [updated] = await lifecycle.decay_from_evidence("fact", evidence)

    stored = await store.get(loop.id)
    assert updated == stored
    assert stored.state is LoopState.DRIFTING
    assert stored.confidence < 0.9
    assert stored.confidence_prior == pytest.approx(0.9, abs=1e-6)
    assert str(evidence) in stored.drift_rationale


async def test_decay_after_the_sweep_keeps_the_sweep_rationale(
    pg_pool, lifecycle, store
):
    loop = await make_loop(
        pg_pool, state=LoopState.ACTIVE, deadline=utcnow() - timedelta(days=1)
    )
    evidence = await link_evidence(pg_pool, loop.id, kind="fact")
    drifted = await lifecycle.drift(loop.id)
    assert drifted.state is LoopState.DRIFTING

    await lifecycle.decay_from_evidence("fact", evidence)

    stored = await store.get(loop.id)
    assert stored.state is LoopState.DRIFTING
    assert stored.drift_rationale == drifted.drift_rationale
    assert stored.confidence < 0.9


@pytest.mark.parametrize(
    "state",
    [LoopState.SUSPECTED, LoopState.DRIFTING, LoopState.CLOSED, LoopState.DROPPED],
)
async def test_decay_changes_only_the_confidence_outside_active(
    pg_pool, lifecycle, store, state
):
    loop = await make_loop(pg_pool, state=state, confidence=0.8, rationale="kept")
    evidence = await link_evidence(pg_pool, loop.id, kind="fact")

    await lifecycle.decay_from_evidence("fact", evidence)

    stored = await store.get(loop.id)
    assert stored.state is state
    assert stored.drift_rationale == "kept"
    assert stored.confidence < 0.8


async def test_decay_with_a_second_evidence_link_keeps_part_of_the_confidence(
    pg_pool, lifecycle, store
):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.8)
    gone = await link_evidence(pg_pool, loop.id, kind="fact")
    await link_evidence(pg_pool, loop.id, kind="episode")

    await lifecycle.decay_from_evidence("fact", gone)

    expected = _decayed(0.8, remaining=1, total=2)
    assert 0 < expected < 0.8
    assert (await store.get(loop.id)).confidence == pytest.approx(expected, abs=1e-6)


async def test_two_concurrent_decays_compose(pg_pool, lifecycle, store):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.8)
    first = await link_evidence(pg_pool, loop.id, kind="fact")
    second = await link_evidence(pg_pool, loop.id, kind="fact")
    await link_evidence(pg_pool, loop.id, kind="episode")

    await asyncio.gather(
        lifecycle.decay_from_evidence("fact", first),
        lifecycle.decay_from_evidence("fact", second),
    )

    once = _decayed(0.8, remaining=2, total=3)
    assert (await store.get(loop.id)).confidence == pytest.approx(
        _decayed(once, remaining=2, total=3), abs=1e-6
    )


async def test_decay_for_evidence_no_loop_cites_changes_nothing(lifecycle):
    assert await lifecycle.decay_from_evidence("fact", uuid4()) == []


# ── drift ─────────────────────────────────────────────────────────────────────


async def test_drift_moves_an_active_loop_past_its_deadline(pg_pool, lifecycle, store):
    loop = await make_loop(
        pg_pool, state=LoopState.ACTIVE, deadline=utcnow() - timedelta(days=1)
    )

    drifted = await lifecycle.drift(loop.id)

    assert drifted == await store.get(loop.id)
    assert drifted.state is LoopState.DRIFTING
    assert "before the implied window elapsed" in drifted.drift_rationale


async def test_drift_skips_a_loop_confirmed_again_after_the_candidate_read(
    pg_pool, lifecycle, store
):
    loop = await make_loop(
        pg_pool, state=LoopState.ACTIVE, deadline=utcnow() + timedelta(days=3)
    )
    assert await lifecycle.drift(loop.id) is None
    assert (await store.get(loop.id)).state is LoopState.ACTIVE


@pytest.mark.parametrize(
    "state",
    [LoopState.SUSPECTED, LoopState.DRIFTING, LoopState.CLOSED, LoopState.DROPPED],
)
async def test_drift_ignores_every_other_state(pg_pool, lifecycle, state):
    loop = await make_loop(pg_pool, state=state, deadline=utcnow() - timedelta(days=1))
    assert await lifecycle.drift(loop.id) is None
