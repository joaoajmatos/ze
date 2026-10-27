"""Every lifecycle event against a real Postgres (spec FR-012, SC-001, SC-004).

US1 part: confirm, close, drop, expire, decay and drift each write atomically.
"""

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import pytest
from ze_agents.claims import DecayProfile, decay
from ze_plugin.contribution import EvidenceRef
from ze_plugin.contribution import DanglingEvidenceError
from ze_worldstate.errors import InvalidLoopTransitionError, LoopNotFoundError
from ze_worldstate.fingerprint import compute_evidence_fingerprint
from ze_worldstate.lifecycle import (
    Corroboration,
    LoopDraft,
    LoopLifecycle,
    SourceWrite,
)
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopSourceRole, LoopState, SourceKey, TrackOutcome

from tests.pg._builders import (
    fail_writes_to,
    link_evidence,
    make_episode,
    make_goal_with_gates,
    make_loop,
    seed_source,
    utcnow,
)

pytestmark = pytest.mark.pg


def _decayed(confidence: float, *, remaining: int, total: int) -> float:
    return decay(
        confidence,
        DecayProfile.EVIDENCE_WEIGHTED,
        remaining_evidence=remaining,
        total_evidence=total,
    )


@pytest.fixture
def memory_store():
    """Every episode and fact id exists, as far as the contribution seam can tell."""
    return SimpleNamespace(
        get_episodes_by_ids=AsyncMock(side_effect=lambda ids: list(ids)),
        get_facts_by_ids=AsyncMock(side_effect=lambda ids: list(ids)),
    )


@pytest.fixture
def lifecycle(pg_pool, memory_store) -> LoopLifecycle:
    return LoopLifecycle(pg_pool, memory_store=memory_store)


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


async def test_drop_leaves_the_loops_sources_untouched(pg_pool, lifecycle, store):
    loop = await make_loop(pg_pool, state=LoopState.ACTIVE)
    await seed_source(pg_pool, loop.id, "conversation", "t1", role="origin")
    await seed_source(pg_pool, loop.id, "email", "m1", promoted=True)
    before = [(s.key, s.promoted) for s in await store.list_sources(loop.id)]

    await lifecycle.drop(loop.id)

    assert [(s.key, s.promoted) for s in await store.list_sources(loop.id)] == before


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


# ═════════════════════════════ US2: every way in and out ═════════════════════


async def _counts(pool) -> tuple[int, int, int]:
    async with pool.acquire() as conn:
        return (
            await conn.fetchval("SELECT count(*) FROM open_loops"),
            await conn.fetchval("SELECT count(*) FROM memory_relationships"),
            await conn.fetchval("SELECT count(*) FROM open_loop_sources"),
        )


def _episode(episode_id) -> EvidenceRef:
    return EvidenceRef(kind="episode", id=episode_id)


# ── create ────────────────────────────────────────────────────────────────────


async def test_create_suspected_writes_row_links_and_origin_together(
    pg_pool, lifecycle, store
):
    episode_id = await make_episode(pg_pool)
    entity_id = uuid4()
    draft = LoopDraft(
        "Renew passport",
        "email",
        evidence=(_episode(episode_id),),
        entity_ids=(entity_id,),
        source=SourceKey("email", "msg-1"),
    )

    created = await lifecycle.create_suspected(draft)

    assert created == await store.get(created.id)
    assert created.state is LoopState.SUSPECTED
    assert created.confidence == pytest.approx(0.3, abs=1e-6)
    assert [e.id for e in await store.list_evidence(created.id)] == [episode_id]
    [origin] = await store.list_sources(created.id)
    assert origin.role is LoopSourceRole.ORIGIN
    assert origin.key == SourceKey("email", "msg-1")
    assert origin.evidence == _episode(episode_id)
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval(
            "SELECT count(*) FROM memory_relationships WHERE source_id = $1"
            " AND predicate = 'has_open_loop' AND target_id = $2",
            entity_id,
            created.id,
        ) == 1


async def test_create_declared_stamps_and_links_in_one_write(pg_pool, lifecycle, store):
    episode_id = await make_episode(pg_pool)
    draft = LoopDraft(
        "Renew passport",
        "user_declared",
        evidence=(_episode(episode_id),),
        source=SourceKey("conversation", "thread-1"),
    )

    created = await lifecycle.create_declared(draft, window_days=3)

    assert created == await store.get(created.id)
    assert created.state is LoopState.ACTIVE
    assert created.confidence == pytest.approx(0.9, abs=1e-6)
    assert created.confirmed_at is not None
    assert created.drift_rationale is None
    assert abs((created.drift_deadline - (utcnow() + timedelta(days=3))).total_seconds()) < 60
    assert [e.id for e in await store.list_evidence(created.id)] == [episode_id]
    assert len(await store.list_sources(created.id)) == 1


@pytest.mark.parametrize("declared", [False, True])
async def test_create_with_the_source_write_failing_writes_nothing(
    pg_pool, lifecycle, declared
):
    episode_id = await make_episode(pg_pool)
    draft = LoopDraft(
        "Renew passport",
        "email",
        evidence=(_episode(episode_id),),
        entity_ids=(uuid4(),),
        source=SourceKey("email", "msg-1"),
    )
    before = await _counts(pg_pool)
    await fail_writes_to(pg_pool, "open_loop_sources")

    create = lifecycle.create_declared if declared else lifecycle.create_suspected
    with pytest.raises(asyncpg.PostgresError):
        await create(draft)

    assert await _counts(pg_pool) == before


async def test_create_with_the_link_write_failing_writes_nothing(pg_pool, lifecycle):
    episode_id = await make_episode(pg_pool)
    draft = LoopDraft(
        "Renew passport", "email", evidence=(_episode(episode_id),), entity_ids=(uuid4(),)
    )
    before = await _counts(pg_pool)
    await fail_writes_to(pg_pool, "memory_relationships")

    with pytest.raises(asyncpg.PostgresError):
        await lifecycle.create_suspected(draft)

    assert await _counts(pg_pool) == before


@pytest.mark.parametrize("declared", [False, True])
async def test_both_creates_check_that_their_evidence_exists(
    pg_pool, memory_store, declared
):
    memory_store.get_episodes_by_ids = AsyncMock(return_value=[])
    lifecycle = LoopLifecycle(pg_pool, memory_store=memory_store)
    draft = LoopDraft("Renew passport", "email", evidence=(_episode(uuid4()),))
    create = lifecycle.create_declared if declared else lifecycle.create_suspected

    with pytest.raises(DanglingEvidenceError):
        await create(draft)

    assert await _counts(pg_pool) == (0, 0, 0)


async def test_both_creates_put_their_evidence_on_the_contribution(
    pg_pool, lifecycle, monkeypatch
):
    seen = []
    from ze_worldstate.lifecycle import events

    real = events.submit_and_detect_collisions

    async def spy(contribution, write, **kwargs):
        seen.append(contribution)
        return await real(contribution, write, **kwargs)

    monkeypatch.setattr(events, "submit_and_detect_collisions", spy)
    episode_id = await make_episode(pg_pool)
    draft = LoopDraft("Renew passport", "email", evidence=(_episode(episode_id),))

    await lifecycle.create_suspected(draft)
    await lifecycle.create_declared(draft)

    assert [c.evidence for c in seen] == [[_episode(episode_id)]] * 2


async def test_track_style_and_inflow_style_declared_creates_stamp_alike(
    pg_pool, lifecycle
):
    tracked = await lifecycle.create_declared(
        LoopDraft(
            "Keep an eye on the budget",
            "user_declared",
            source=SourceKey("conversation", "thread-1"),
        ),
        window_days=7,
    )
    episode_id = await make_episode(pg_pool)
    inflow = await lifecycle.create_declared(
        LoopDraft(
            "Send the invoice",
            "user_declared",
            evidence=(_episode(episode_id),),
            source=SourceKey("conversation", "thread-2"),
        )
    )

    for field in ("state", "provenance", "confidence", "drift_rationale"):
        assert getattr(tracked, field) == getattr(inflow, field)
    assert tracked.confirmed_at is not None and inflow.confirmed_at is not None
    assert abs((tracked.drift_deadline - inflow.drift_deadline).total_seconds()) < 60


async def test_create_declared_and_confirm_stamp_the_same_fields(pg_pool, lifecycle):
    created = await lifecycle.create_declared(LoopDraft("Renew", "user_declared"))
    suspected = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)

    confirmed = await lifecycle.confirm(suspected.id)

    assert confirmed.confidence == created.confidence
    assert confirmed.drift_rationale == created.drift_rationale is None
    assert abs((confirmed.drift_deadline - created.drift_deadline).total_seconds()) < 60


# ── track ─────────────────────────────────────────────────────────────────────


async def test_track_confirms_a_suspected_loop(pg_pool, lifecycle, store):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    entity_id = uuid4()

    tracked = await lifecycle.track(loop.id, window_days=14, entity_ids=[entity_id])

    assert tracked.outcome == TrackOutcome.CONFIRMED
    assert tracked.loop == await store.get(loop.id)
    assert tracked.loop.state is LoopState.ACTIVE
    assert tracked.loop.confidence == pytest.approx(0.9, abs=1e-6)
    assert abs((tracked.loop.drift_deadline - (utcnow() + timedelta(days=14))).total_seconds()) < 60


async def test_track_revives_a_drifting_loop(pg_pool, lifecycle):
    loop = await make_loop(
        pg_pool, state=LoopState.DRIFTING, confidence=0.5, rationale="No evidence"
    )

    tracked = await lifecycle.track(loop.id, window_days=7)

    assert tracked.outcome == TrackOutcome.REVIVED
    assert tracked.loop.state is LoopState.ACTIVE
    assert tracked.loop.drift_rationale is None
    assert tracked.loop.confidence == pytest.approx(0.9, abs=1e-6)


async def test_track_reinforces_an_active_loop_without_touching_its_deadline(
    pg_pool, lifecycle
):
    deadline = utcnow() + timedelta(days=2)
    loop = await make_loop(pg_pool, confidence=0.6, deadline=deadline)

    tracked = await lifecycle.track(loop.id, window_days=30)

    assert tracked.outcome == TrackOutcome.REINFORCED
    assert tracked.loop.confidence == pytest.approx(0.9, abs=1e-6)
    assert tracked.loop.drift_deadline == deadline


async def test_track_never_lowers_an_active_loops_confidence(pg_pool, lifecycle):
    loop = await make_loop(pg_pool, confidence=0.95)
    tracked = await lifecycle.track(loop.id, window_days=7)
    assert tracked.loop.confidence == pytest.approx(0.95, abs=1e-6)


@pytest.mark.parametrize("state", [LoopState.CLOSED, LoopState.DROPPED])
async def test_track_is_refused_on_a_terminal_loop(pg_pool, lifecycle, state):
    loop = await make_loop(pg_pool, state=state)
    with pytest.raises(InvalidLoopTransitionError):
        await lifecycle.track(loop.id, window_days=7)


async def test_track_with_the_entity_link_failing_leaves_a_drifting_loop_drifting(
    pg_pool, lifecycle, store
):
    loop = await make_loop(pg_pool, state=LoopState.DRIFTING, confidence=0.5)
    await fail_writes_to(pg_pool, "memory_relationships")

    with pytest.raises(asyncpg.PostgresError):
        await lifecycle.track(loop.id, window_days=7, entity_ids=[uuid4()])

    stored = await store.get(loop.id)
    assert stored.state is LoopState.DRIFTING
    assert stored.confidence == pytest.approx(0.5, abs=1e-6)


# ── note evidence ─────────────────────────────────────────────────────────────


async def test_note_evidence_moves_an_active_deadline_forward_with_evidence(
    pg_pool, lifecycle, store
):
    loop = await make_loop(pg_pool, deadline=utcnow() - timedelta(days=2))
    episode_id = await make_episode(pg_pool)

    noted = await lifecycle.note_evidence(
        loop.id, evidence=[_episode(episode_id)], entity_ids=[uuid4()]
    )

    assert noted == await store.get(loop.id)
    assert noted.drift_deadline >= utcnow() + timedelta(days=7) - timedelta(minutes=1)
    assert [e.id for e in await store.list_evidence(loop.id)] == [episode_id]


async def test_note_evidence_without_evidence_leaves_the_deadline(pg_pool, lifecycle):
    deadline = utcnow() - timedelta(days=2)
    loop = await make_loop(pg_pool, deadline=deadline)

    noted = await lifecycle.note_evidence(loop.id, evidence=[], entity_ids=[uuid4()])

    assert noted.drift_deadline == deadline


async def test_note_evidence_never_lowers_a_later_deadline(pg_pool, lifecycle):
    far = utcnow() + timedelta(days=30)
    loop = await make_loop(pg_pool, deadline=far)
    episode_id = await make_episode(pg_pool)

    noted = await lifecycle.note_evidence(
        loop.id, evidence=[_episode(episode_id)], entity_ids=[]
    )

    assert noted.drift_deadline == far


@pytest.mark.parametrize("state", [LoopState.SUSPECTED, LoopState.DRIFTING])
async def test_note_evidence_only_links_a_suspected_or_drifting_loop(
    pg_pool, lifecycle, store, state
):
    past = utcnow() - timedelta(days=2)
    loop = await make_loop(pg_pool, state=state, deadline=past, confidence=0.4)
    episode_id = await make_episode(pg_pool)

    noted = await lifecycle.note_evidence(
        loop.id, evidence=[_episode(episode_id)], entity_ids=[]
    )

    assert noted.state is state
    assert noted.drift_deadline == past
    assert len(await store.list_evidence(loop.id)) == 1


@pytest.mark.parametrize("state", [LoopState.CLOSED, LoopState.DROPPED])
async def test_note_evidence_is_refused_on_a_terminal_loop(pg_pool, lifecycle, state):
    loop = await make_loop(pg_pool, state=state)
    with pytest.raises(InvalidLoopTransitionError):
        await lifecycle.note_evidence(loop.id, evidence=[], entity_ids=[])


# ── corroborate and promote ───────────────────────────────────────────────────


def _corroboration(episode_id, ref="msg-2", confidence=0.45) -> Corroboration:
    return Corroboration(
        evidence=(_episode(episode_id),),
        entity_ids=(uuid4(),),
        key=SourceKey("email", ref),
        same_concern=0.8,
        confidence=confidence,
        model="m",
        latency_ms=12,
    )


async def test_corroborate_writes_links_source_and_confidence(pg_pool, lifecycle, store):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    episode_id = await make_episode(pg_pool)

    written = await lifecycle.corroborate(loop.id, _corroboration(episode_id))

    assert written.outcome == "corroborate"
    assert written.loop == await store.get(loop.id)
    assert written.loop.state is LoopState.SUSPECTED
    assert written.loop.confidence == pytest.approx(0.45, abs=1e-6)
    assert written.loop.confidence_prior == pytest.approx(0.3, abs=1e-6)
    [source] = await store.list_sources(loop.id)
    assert source.role is LoopSourceRole.CORROBORATION
    assert source.same_concern == pytest.approx(0.8, abs=1e-6)
    assert source.promoted is False
    assert source.model == "m" and source.latency_ms == 12


async def test_corroborate_with_a_duplicate_source_writes_no_confidence(
    pg_pool, lifecycle
):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    episode_id = await make_episode(pg_pool)
    await lifecycle.corroborate(loop.id, _corroboration(episode_id, confidence=0.4))

    again = await lifecycle.corroborate(loop.id, _corroboration(episode_id, confidence=0.55))

    assert again.outcome == "duplicate_source"
    assert again.loop.confidence == pytest.approx(0.4, abs=1e-6)


@pytest.mark.parametrize(
    "state", [LoopState.ACTIVE, LoopState.DRIFTING, LoopState.CLOSED, LoopState.DROPPED]
)
async def test_corroborate_is_refused_unless_suspected(pg_pool, lifecycle, state):
    loop = await make_loop(pg_pool, state=state)
    with pytest.raises(InvalidLoopTransitionError):
        await lifecycle.corroborate(loop.id, _corroboration(uuid4()))


async def test_corroborate_with_the_source_write_failing_changes_nothing(
    pg_pool, lifecycle, store
):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    episode_id = await make_episode(pg_pool)
    await fail_writes_to(pg_pool, "open_loop_sources")

    with pytest.raises(asyncpg.PostgresError):
        await lifecycle.corroborate(loop.id, _corroboration(episode_id))

    assert (await store.get(loop.id)).confidence == pytest.approx(0.3, abs=1e-6)
    assert await store.list_evidence(loop.id) == []


async def test_promote_stamps_and_marks_the_source(pg_pool, lifecycle, store):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    episode_id = await make_episode(pg_pool)

    written = await lifecycle.promote(loop.id, _corroboration(episode_id))

    assert written.outcome == "promote"
    assert written.loop == await store.get(loop.id)
    assert written.loop.state is LoopState.ACTIVE
    assert written.loop.confidence == pytest.approx(0.7, abs=1e-6)
    assert written.loop.confirmed_at is not None
    assert written.loop.drift_rationale is None
    assert abs((written.loop.drift_deadline - (utcnow() + timedelta(days=7))).total_seconds()) < 60
    [source] = await store.list_sources(loop.id)
    assert source.promoted is True


async def test_promote_keeps_a_higher_confidence(pg_pool, lifecycle):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.75)
    episode_id = await make_episode(pg_pool)
    written = await lifecycle.promote(loop.id, _corroboration(episode_id))
    assert written.loop.confidence == pytest.approx(0.75, abs=1e-6)


async def test_two_concurrent_promotes_give_one_winner_and_the_loser_lowers_nothing(
    pg_pool, lifecycle, store
):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    first = await make_episode(pg_pool)
    second = await make_episode(pg_pool)

    results: list[SourceWrite] = await asyncio.gather(
        lifecycle.promote(loop.id, _corroboration(first, ref="a", confidence=0.5)),
        lifecycle.promote(loop.id, _corroboration(second, ref="b", confidence=0.5)),
    )

    assert sorted(r.outcome for r in results) == ["lost_race", "promote"]
    stored = await store.get(loop.id)
    assert stored.state is LoopState.ACTIVE
    assert stored.confidence == pytest.approx(0.7, abs=1e-6)
    sources = await store.list_sources(loop.id)
    assert sorted(s.promoted for s in sources) == [False, True]


async def test_promote_with_the_source_write_failing_keeps_the_loop_suspected(
    pg_pool, lifecycle, store
):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    episode_id = await make_episode(pg_pool)
    await fail_writes_to(pg_pool, "open_loop_sources")

    with pytest.raises(asyncpg.PostgresError):
        await lifecycle.promote(loop.id, _corroboration(episode_id))

    stored = await store.get(loop.id)
    assert stored.state is LoopState.SUSPECTED
    assert stored.confidence == pytest.approx(0.3, abs=1e-6)


@pytest.mark.parametrize("state", [LoopState.CLOSED, LoopState.DROPPED])
async def test_promote_is_refused_on_a_terminal_loop(pg_pool, lifecycle, state):
    loop = await make_loop(pg_pool, state=state)
    with pytest.raises(InvalidLoopTransitionError):
        await lifecycle.promote(loop.id, _corroboration(uuid4()))


# ── resolve ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "state", [LoopState.SUSPECTED, LoopState.ACTIVE, LoopState.DRIFTING]
)
async def test_resolve_closes_a_live_loop_with_evidence_and_no_fingerprint(
    pg_pool, lifecycle, store, state
):
    loop = await make_loop(pg_pool, state=state, confidence=0.5)
    episode_id = await make_episode(pg_pool)

    closed = await lifecycle.resolve(loop.id, evidence=[_episode(episode_id)])

    assert closed == await store.get(loop.id)
    assert closed.state is LoopState.CLOSED
    assert closed.closed_at is not None
    assert closed.dismissed_evidence_fingerprint is None
    assert [e.id for e in await store.list_evidence(loop.id)] == [episode_id]


@pytest.mark.parametrize("state", [LoopState.CLOSED, LoopState.DROPPED])
async def test_resolve_leaves_a_terminal_loop_alone(pg_pool, lifecycle, store, state):
    loop = await make_loop(pg_pool, state=state)
    assert await lifecycle.resolve(loop.id, evidence=[]) is None
    assert (await store.get(loop.id)).state is state


async def test_resolve_on_a_missing_loop_raises_not_found(lifecycle):
    with pytest.raises(LoopNotFoundError):
        await lifecycle.resolve(uuid4(), evidence=[])


async def test_resolve_with_the_link_write_failing_keeps_the_loop_open(
    pg_pool, lifecycle, store
):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    episode_id = await make_episode(pg_pool)
    await fail_writes_to(pg_pool, "memory_relationships")

    with pytest.raises(asyncpg.PostgresError):
        await lifecycle.resolve(loop.id, evidence=[_episode(episode_id)])

    stored = await store.get(loop.id)
    assert stored.state is LoopState.SUSPECTED
    assert stored.closed_at is None


# ── link ──────────────────────────────────────────────────────────────────────


async def test_link_sets_the_reminder_then_the_goal_and_never_overwrites(
    pg_pool, lifecycle, store
):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    reminder, other = uuid4(), uuid4()
    goal = await make_goal_with_gates(pg_pool)
    other_goal = await make_goal_with_gates(pg_pool, title="Other")

    assert await lifecycle.link(loop.id, reminder_id=reminder) is True
    assert await lifecycle.link(loop.id, goal_id=goal) is True
    assert await lifecycle.link(loop.id, reminder_id=other, goal_id=other_goal) is False

    stored = await store.get(loop.id)
    assert stored.reminder_id == reminder and stored.goal_id == goal


async def test_link_with_nothing_to_link_changes_nothing(pg_pool, lifecycle):
    loop = await make_loop(pg_pool)
    assert await lifecycle.link(loop.id) is False


@pytest.mark.parametrize("state", [LoopState.CLOSED, LoopState.DROPPED])
async def test_link_returns_false_on_a_terminal_loop(pg_pool, lifecycle, state):
    loop = await make_loop(pg_pool, state=state)
    assert await lifecycle.link(loop.id, reminder_id=uuid4()) is False
