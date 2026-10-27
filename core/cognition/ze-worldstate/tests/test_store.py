"""The loop store is reads only; every write is a `LoopLifecycle` event (real-Postgres tests)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ze_plugin.contribution import EvidenceRef

from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopProvenance, LoopSourceRole, LoopState, SourceKey
from tests.conftest import make_pool

def _row(**overrides) -> dict:
    base = {
        "id": uuid4(),
        "title": "Renew passport",
        "state": "suspected",
        "provenance": "conversation",
        "confidence": 0.3,
        "goal_id": None,
        "reminder_id": None,
        "confidence_prior": None,
        "confidence_changed_at": None,
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


async def test_list_drift_candidates_filters_on_the_deadline_alone():
    pool, conn = make_pool(fetch=[])
    await PostgresLoopStore(pool=pool).list_drift_candidates()

    sql = conn.fetch.await_args.args[0]
    assert "drift_deadline <= now()" in sql
    assert "updated_at" not in sql
    assert "confirmed_at" not in sql


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


async def test_row_carries_reminder_id():
    reminder_id = uuid4()
    pool, _ = make_pool(fetchrow=_row(reminder_id=reminder_id))
    loop = await PostgresLoopStore(pool=pool).get(uuid4())
    assert loop.reminder_id == reminder_id


async def test_row_maps_state_and_provenance():
    pool, _ = make_pool(fetchrow=_row(state="drifting", provenance="email"))
    loop = await PostgresLoopStore(pool=pool).get(uuid4())
    assert loop.state is LoopState.DRIFTING
    assert loop.provenance == "email"
    assert LoopProvenance.CONVERSATION == "conversation"


async def test_source_row_with_evidence_maps_the_ref():
    row = _source_row()
    pool, _ = make_pool(fetch=[row])
    [source] = await PostgresLoopStore(pool=pool).list_sources(row["loop_id"])
    assert source.key == SourceKey("email", "thread-1")
    assert source.role is LoopSourceRole.CORROBORATION
    assert source.evidence == EvidenceRef(kind="episode", id=row["evidence_id"])


def test_the_store_has_no_write_methods():
    writes = [
        name
        for name in dir(PostgresLoopStore)
        if name.startswith(("create", "transition", "link", "set_", "stamp", "promote",
                            "mark_", "add_", "record_", "resolve"))
    ]
    assert writes == []
