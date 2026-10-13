from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from ze_worldstate.errors import InvalidLoopTransitionError, LoopNotFoundError
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopClaimKind, LoopProvenance, LoopState, OpenLoop
from tests.conftest import make_pool


def _row(**overrides) -> dict:
    base = {
        "id": uuid4(),
        "title": "Renew passport",
        "state": "suspected",
        "claim_kind": "suspicion",
        "provenance": "conversation",
        "confidence": 0.3,
        "goal_id": None,
        "dismissed_evidence_fingerprint": None,
        "drift_deadline": None,
        "drift_rationale": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "confirmed_at": None,
        "closed_at": None,
    }
    base.update(overrides)
    return base


async def test_create_returns_loop():
    row = _row()
    pool, conn = make_pool(fetchrow=row)
    store = PostgresLoopStore(pool=pool)

    loop = OpenLoop(
        title="Renew passport",
        claim_kind=LoopClaimKind.SUSPICION,
        provenance=LoopProvenance.CONVERSATION,
        confidence=0.3,
    )
    result = await store.create(loop)

    assert result.id == row["id"]
    assert result.state == LoopState.SUSPECTED
    conn.fetchrow.assert_awaited_once()


async def test_get_returns_none_when_missing():
    pool, conn = make_pool(fetchrow=None)
    store = PostgresLoopStore(pool=pool)
    assert await store.get(uuid4()) is None


async def test_list_filters_by_states():
    pool, conn = make_pool(fetch=[_row(), _row(state="active")])
    store = PostgresLoopStore(pool=pool)
    loops = await store.list(["suspected", "active"])
    assert len(loops) == 2
    conn.fetch.assert_awaited_once()


@pytest.mark.parametrize(
    "from_state,to_state",
    [
        ("suspected", "active"),
        ("suspected", "dropped"),
        ("active", "drifting"),
        ("active", "closed"),
        ("active", "dropped"),
        ("drifting", "closed"),
        ("drifting", "dropped"),
    ],
)
async def test_transition_allows_phase_a_matrix(from_state, to_state):
    loop_id = uuid4()
    get_row = _row(id=loop_id, state=from_state)
    updated_row = _row(id=loop_id, state=to_state)
    pool, conn = make_pool(fetchrow=get_row)
    store = PostgresLoopStore(pool=pool)

    # First fetchrow call is the internal `get`, second is the UPDATE ... RETURNING.
    conn.fetchrow = _sequenced_fetchrow([get_row, updated_row])

    result = await store.transition(loop_id, to_state)
    assert result.state == LoopState(to_state)


async def test_transition_rejects_drifting_to_active():
    loop_id = uuid4()
    get_row = _row(id=loop_id, state="drifting")
    pool, conn = make_pool(fetchrow=get_row)
    store = PostgresLoopStore(pool=pool)

    with pytest.raises(InvalidLoopTransitionError):
        await store.transition(loop_id, "active")


async def test_transition_raises_not_found():
    pool, conn = make_pool(fetchrow=None)
    store = PostgresLoopStore(pool=pool)
    with pytest.raises(LoopNotFoundError):
        await store.transition(uuid4(), "active")


def _sequenced_fetchrow(rows: list[dict]):
    from unittest.mock import AsyncMock

    it = iter(rows)

    async def _fn(*args, **kwargs):
        return next(it)

    return AsyncMock(side_effect=_fn)


async def test_link_entity_and_evidence_insert_relationship_rows():
    pool, conn = make_pool()
    store = PostgresLoopStore(pool=pool)

    await store.link_entity(uuid4(), uuid4())
    await store.link_evidence(uuid4(), "fact", uuid4())

    # link_entity: 1 insert. link_evidence: 1 insert + 1 updated_at bump (drift signal).
    assert conn.execute.await_count == 3


async def test_count_evidence_links():
    pool, conn = make_pool(fetchrow={"n": 3})
    store = PostgresLoopStore(pool=pool)
    assert await store.count_evidence_links(uuid4()) == 3


async def test_list_evidence():
    pool, conn = make_pool(fetch=[{"target_type": "fact", "target_id": uuid4()}])
    store = PostgresLoopStore(pool=pool)
    refs = await store.list_evidence(uuid4())
    assert len(refs) == 1
    assert refs[0].kind == "fact"


async def test_transition_user_asked_revives_drifting():
    loop_id = uuid4()
    get_row = _row(id=loop_id, state="drifting")
    updated_row = _row(id=loop_id, state="active")
    pool, conn = make_pool(fetchrow=get_row)
    store = PostgresLoopStore(pool=pool)
    conn.fetchrow = _sequenced_fetchrow([get_row, updated_row])

    result = await store.transition(loop_id, "active", user_asked=True)
    assert result.state == LoopState.ACTIVE


@pytest.mark.parametrize(
    "from_state,to_state",
    [
        ("closed", "active"),
        ("dropped", "active"),
        ("suspected", "drifting"),
    ],
)
async def test_user_asked_does_not_widen_other_edges(from_state, to_state):
    loop_id = uuid4()
    pool, conn = make_pool(fetchrow=_row(id=loop_id, state=from_state))
    store = PostgresLoopStore(pool=pool)

    with pytest.raises(InvalidLoopTransitionError):
        await store.transition(loop_id, to_state, user_asked=True)


async def test_stamp_declared_writes_exact_field_set():
    loop_id = uuid4()
    pool, conn = make_pool(fetchrow={"id": loop_id})
    store = PostgresLoopStore(pool=pool)
    deadline = datetime.now(timezone.utc)

    await store.stamp_declared(loop_id, confidence=0.9, deadline=deadline)

    conn.fetchrow.assert_awaited_once()
    sql = " ".join(conn.fetchrow.await_args.args[0].split()).lower()
    assert "confidence" in sql
    assert "drift_deadline" in sql
    assert "drift_rationale = null" in sql
    assert "confirmed_at = now()" in sql
    assert "updated_at = now()" in sql
    assert "state =" not in sql
    assert "provenance" not in sql
    assert "claim_kind" not in sql


async def test_stamp_declared_raises_not_found():
    pool, conn = make_pool(fetchrow=None)
    store = PostgresLoopStore(pool=pool)

    with pytest.raises(LoopNotFoundError):
        await store.stamp_declared(
            uuid4(), confidence=0.9, deadline=datetime.now(timezone.utc)
        )


async def test_list_drift_candidates_filters_on_the_deadline_alone():
    pool, conn = make_pool(fetch=[])
    await PostgresLoopStore(pool=pool).list_drift_candidates()

    sql = conn.fetch.await_args.args[0]
    assert "drift_deadline <= now()" in sql
    assert "updated_at" not in sql
    assert "confirmed_at" not in sql


async def test_record_corroboration_only_moves_active_deadlines_forward():
    pool, conn = make_pool()
    await PostgresLoopStore(pool=pool).record_corroboration(uuid4(), window_days=7)

    conn.execute.assert_awaited_once()
    sql, _loop_id, window = conn.execute.await_args.args
    assert "GREATEST" in sql
    assert "state = 'active'" in sql
    assert window == 7
