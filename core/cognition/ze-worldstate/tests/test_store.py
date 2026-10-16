from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from ze_plugin.contribution import EvidenceRef

from ze_worldstate.errors import InvalidLoopTransitionError, LoopNotFoundError
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import (
    LoopClaimKind,
    LoopProvenance,
    LoopSource,
    LoopSourceRole,
    LoopState,
    OpenLoop,
    SourceKey,
)
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
        "reminder_id": None,
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


def _source_row(**overrides) -> dict:
    base = {
        "id": uuid4(),
        "loop_id": uuid4(),
        "role": "corroboration",
        "inflow": "email",
        "source_ref": "thread-1",
        "evidence_kind": "episode",
        "evidence_id": uuid4(),
        "same_concern": 0.8,
        "promoted": False,
        "model": "m",
        "latency_ms": 120,
        "created_at": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return base


def _source(loop_id=None) -> LoopSource:
    return LoopSource(
        loop_id=loop_id or uuid4(),
        role=LoopSourceRole.CORROBORATION,
        key=SourceKey("email", "thread-1"),
        evidence=EvidenceRef(kind="episode", id=uuid4()),
        same_concern=0.8,
        model="m",
        latency_ms=120,
    )


async def test_add_source_inserts_and_returns_the_row():
    row = _source_row()
    pool, conn = make_pool(fetchrow=row)
    result = await PostgresLoopStore(pool=pool).add_source(_source(row["loop_id"]))

    sql = " ".join(conn.fetchrow.await_args.args[0].split())
    assert "ON CONFLICT (loop_id, inflow, source_ref) DO NOTHING RETURNING" in sql
    assert result is not None
    assert result.key == SourceKey("email", "thread-1")
    assert result.role is LoopSourceRole.CORROBORATION
    assert result.evidence == EvidenceRef(kind="episode", id=row["evidence_id"])


async def test_add_source_returns_none_on_conflict():
    pool, _conn = make_pool(fetchrow=None)
    assert await PostgresLoopStore(pool=pool).add_source(_source()) is None


async def test_list_sources_orders_by_created_at():
    pool, conn = make_pool(
        fetch=[_source_row(), _source_row(evidence_kind=None, evidence_id=None)]
    )
    sources = await PostgresLoopStore(pool=pool).list_sources(uuid4())

    assert "ORDER BY created_at" in conn.fetch.await_args.args[0]
    assert len(sources) == 2
    assert sources[1].evidence is None


async def test_list_sources_for_is_one_query_grouped_by_loop():
    a, b = uuid4(), uuid4()
    pool, conn = make_pool(
        fetch=[
            _source_row(loop_id=a),
            _source_row(loop_id=b),
            _source_row(loop_id=a, inflow="chat"),
        ]
    )
    grouped = await PostgresLoopStore(pool=pool).list_sources_for([a, b])

    conn.fetch.assert_awaited_once()
    assert "ANY($1)" in conn.fetch.await_args.args[0]
    assert [len(grouped[a]), len(grouped[b])] == [2, 1]


async def test_list_sources_for_empty_makes_no_query():
    pool, conn = make_pool(fetch=[])
    assert await PostgresLoopStore(pool=pool).list_sources_for([]) == {}
    conn.fetch.assert_not_awaited()


async def test_promote_is_a_guarded_single_update():
    row = _row(state="active", confidence=0.7)
    pool, conn = make_pool(fetchrow=row)
    loop = await PostgresLoopStore(pool=pool).promote(
        row["id"], confidence=0.7, window_days=7
    )

    sql = " ".join(conn.fetchrow.await_args.args[0].split())
    assert "WHERE id = $1 AND state = 'suspected'" in sql
    assert "GREATEST(confidence, $2)" in sql
    assert "make_interval(days => $3)" in sql
    assert loop is not None and loop.state is LoopState.ACTIVE


async def test_promote_returns_none_when_not_suspected():
    pool, _conn = make_pool(fetchrow=None)
    assert (
        await PostgresLoopStore(pool=pool).promote(
            uuid4(), confidence=0.7, window_days=7
        )
        is None
    )


async def test_mark_source_promoted_updates_the_row():
    pool, conn = make_pool()
    source_id = uuid4()
    await PostgresLoopStore(pool=pool).mark_source_promoted(source_id)

    sql, arg = conn.execute.await_args.args
    assert "SET promoted = true" in sql
    assert arg == source_id


async def test_row_and_create_carry_reminder_id():
    reminder_id = uuid4()
    pool, conn = make_pool(fetchrow=_row(reminder_id=reminder_id))
    store = PostgresLoopStore(pool=pool)
    loop = OpenLoop(
        title="Call Ana",
        claim_kind=LoopClaimKind.SUSPICION,
        provenance=LoopProvenance.CONVERSATION,
        confidence=0.3,
        reminder_id=reminder_id,
    )
    result = await store.create(loop)
    assert result.reminder_id == reminder_id
    assert reminder_id in conn.fetchrow.await_args.args


async def test_link_sets_pointers_with_coalesce_on_live_loops_only():
    reminder_id, loop_id = uuid4(), uuid4()
    pool, conn = make_pool(fetchrow={"id": loop_id})
    store = PostgresLoopStore(pool=pool)
    assert await store.link(loop_id, reminder_id=reminder_id) is True
    sql, *args = conn.fetchrow.await_args.args
    assert "COALESCE(reminder_id, $2)" in sql and "COALESCE(goal_id, $3)" in sql
    assert "'suspected', 'active', 'drifting'" in sql
    assert args == [loop_id, reminder_id, None]


async def test_link_reports_no_change():
    pool, _ = make_pool(fetchrow=None)
    store = PostgresLoopStore(pool=pool)
    assert await store.link(uuid4(), goal_id=uuid4()) is False


async def test_link_without_a_pointer_is_a_noop():
    pool, conn = make_pool(fetchrow={"id": uuid4()})
    store = PostgresLoopStore(pool=pool)
    assert await store.link(uuid4()) is False
    conn.fetchrow.assert_not_called()
