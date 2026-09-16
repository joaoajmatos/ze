"""Tests for PostgresMemoryStore write paths: propose_events, upsert_entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from ze_memory.graph.store import GraphStore
from ze_memory.retriever import PostgresMemoryStore
from ze_memory.types import Entity, Event


def _make_pool() -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": uuid4()})
    pool.acquire = MagicMock(return_value=_async_ctx(conn))
    return pool, conn


class _async_ctx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_):
        pass


def _make_store(pool=None, graph_store=None) -> tuple[PostgresMemoryStore, AsyncMock]:
    if pool is None:
        pool, conn = _make_pool()
    else:
        conn = pool.acquire.return_value._conn
    store = PostgresMemoryStore.__new__(PostgresMemoryStore)
    store._pool = pool
    store._embedder = None
    store._client = None
    store._graph_store = graph_store
    store._traversal = None
    store._log = MagicMock()
    return store, conn


def _make_graph_store() -> MagicMock:
    gs = MagicMock(spec=GraphStore)
    gs.upsert_relationship = AsyncMock(return_value=uuid4())
    return gs


# ── propose_events ────────────────────────────────────────────────────────────


async def test_propose_events_inserts_each_event():
    pool, conn = _make_pool()
    store, conn = _make_store(pool)
    conn.fetchrow = AsyncMock(return_value={"id": uuid4()})

    events = [
        Event(id=None, event_type="meeting", title="Sprint planning"),
        Event(id=None, event_type="call", title="Customer call"),
    ]
    await store.propose_events(events)

    assert conn.fetchrow.call_count == 2


async def test_propose_events_empty_list_does_nothing():
    pool, conn = _make_pool()
    store, conn = _make_store(pool)
    conn.fetchrow = AsyncMock(return_value={"id": uuid4()})
    await store.propose_events([])
    conn.fetchrow.assert_not_called()


async def test_propose_events_continues_on_single_failure():
    pool, conn = _make_pool()
    store, conn = _make_store(pool)
    conn.fetchrow = AsyncMock(side_effect=[RuntimeError("DB error"), {"id": uuid4()}])

    events = [
        Event(id=None, event_type="meeting", title="Fails"),
        Event(id=None, event_type="call", title="Succeeds"),
    ]
    # Should not raise — second event still processed
    await store.propose_events(events)
    assert conn.fetchrow.call_count == 2


# ── upsert_entity ─────────────────────────────────────────────────────────────


async def test_upsert_entity_returns_id():
    pool, conn = _make_pool()
    store, conn = _make_store(pool)
    new_id = uuid4()
    conn.fetchrow = AsyncMock(return_value={"id": new_id})

    entity = Entity(
        id=None,
        entity_type="person",
        canonical_name="Alice Wonderland",
        aliases=["Alice"],
        attrs={"relationship": "colleague"},
    )
    result = await store.upsert_entity(entity)

    assert result == new_id
    conn.fetchrow.assert_called_once()
    sql = conn.fetchrow.call_args[0][0]
    assert "memory_entities" in sql
    assert "ON CONFLICT" in sql


async def test_upsert_entity_passes_correct_fields():
    pool, conn = _make_pool()
    store, conn = _make_store(pool)
    conn.fetchrow = AsyncMock(return_value={"id": uuid4()})

    entity = Entity(
        id=None,
        entity_type="organisation",
        canonical_name="Acme Corp",
        aliases=["Acme"],
        attrs={"domain": "technology"},
    )
    await store.upsert_entity(entity)

    args = conn.fetchrow.call_args[0]
    assert "organisation" in args
    assert "Acme Corp" in args


# ── get_entity / find_entity_by_name (Phase 130) ────────────────────────────────


async def test_get_entity_returns_none_when_missing():
    pool, conn = _make_pool()
    store, conn = _make_store(pool)
    conn.fetchrow = AsyncMock(return_value=None)

    result = await store.get_entity(uuid4())

    assert result is None


async def test_get_entity_hydrates_entity():
    pool, conn = _make_pool()
    store, conn = _make_store(pool)
    entity_id = uuid4()
    conn.fetchrow = AsyncMock(
        return_value={
            "id": entity_id,
            "entity_type": "project",
            "canonical_name": "Launch",
            "aliases": [],
            "attrs": {},
        }
    )

    result = await store.get_entity(entity_id)

    assert result is not None
    assert result.id == entity_id
    assert result.entity_type == "project"
    assert result.canonical_name == "Launch"


async def test_find_entity_by_name_filters_by_type():
    pool, conn = _make_pool()
    store, conn = _make_store(pool)
    conn.fetchrow = AsyncMock(return_value=None)

    await store.find_entity_by_name("Launch", entity_type="project")

    sql = conn.fetchrow.call_args[0][0]
    assert "entity_type = $2" in sql


async def test_find_entity_by_name_without_type_filter():
    pool, conn = _make_pool()
    store, conn = _make_store(pool)
    conn.fetchrow = AsyncMock(return_value=None)

    await store.find_entity_by_name("Launch")

    sql = conn.fetchrow.call_args[0][0]
    assert "AND entity_type" not in sql


# ── graph relationship creation ───────────────────────────────────────────────


class TestGraphRelationshipCreation:
    async def test_link_fact_describes_edge_when_subject_id_set(self):
        pool, conn = _make_pool()
        gs = _make_graph_store()
        store, _ = _make_store(pool, graph_store=gs)

        subject_id = uuid4()
        fact_id = uuid4()
        from ze_memory.types import Fact

        fact = Fact(
            id=None,
            subject_id=subject_id,
            predicate="likes",
            value="coffee",
            object_text="coffee",
            confidence=0.9,
        )
        await store._link_fact_relationships(fact, fact_id)

        gs.upsert_relationship.assert_awaited()
        calls = gs.upsert_relationship.call_args_list
        predicates = [c[0][0].predicate for c in calls]
        assert "DESCRIBES" in predicates

    async def test_link_fact_sourced_from_edge_when_episode_set(self):
        pool, conn = _make_pool()
        gs = _make_graph_store()
        store, _ = _make_store(pool, graph_store=gs)

        episode_id = uuid4()
        fact_id = uuid4()
        from ze_memory.types import Fact

        fact = Fact(
            id=None,
            subject_id=None,
            predicate="likes",
            value="tea",
            object_text="tea",
            confidence=0.8,
            source_episode_id=episode_id,
        )
        await store._link_fact_relationships(fact, fact_id)

        predicates = [c[0][0].predicate for c in gs.upsert_relationship.call_args_list]
        assert "SOURCED_FROM" in predicates

    async def test_link_fact_no_edges_when_no_subject_or_episode(self):
        pool, conn = _make_pool()
        gs = _make_graph_store()
        store, _ = _make_store(pool, graph_store=gs)

        from ze_memory.types import Fact

        fact = Fact(
            id=None,
            subject_id=None,
            predicate="mood",
            value="happy",
            object_text="happy",
            confidence=0.7,
        )
        await store._link_fact_relationships(fact, uuid4())

        gs.upsert_relationship.assert_not_awaited()

    async def test_link_event_participants_creates_participates_in(self):
        pool, conn = _make_pool()
        gs = _make_graph_store()
        store, _ = _make_store(pool, graph_store=gs)

        event_id = uuid4()
        participant_ids = [uuid4(), uuid4()]
        await store._link_event_participants(event_id, participant_ids)

        assert gs.upsert_relationship.await_count == 2
        predicates = [c[0][0].predicate for c in gs.upsert_relationship.call_args_list]
        assert all(p == "PARTICIPATES_IN" for p in predicates)

    async def test_link_task_state_to_goal_creates_belongs_to_goal(self):
        pool, conn = _make_pool()
        gs = _make_graph_store()
        store, _ = _make_store(pool, graph_store=gs)

        ts_id = uuid4()
        goal_id = uuid4()
        await store._link_task_state_to_goal(ts_id, goal_id)

        gs.upsert_relationship.assert_awaited_once()
        rel = gs.upsert_relationship.call_args[0][0]
        assert rel.predicate == "BELONGS_TO_GOAL"
        assert rel.source_id == ts_id
        assert rel.target_id == goal_id

    async def test_link_episode_entities_creates_mentions_for_matches(self):
        pool, conn = _make_pool()
        gs = _make_graph_store()
        store, _ = _make_store(pool, graph_store=gs)

        import json

        eid = uuid4()
        entity_id = uuid4()
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": entity_id,
                    "canonical_name": "Alice",
                    "aliases": json.dumps(["Al"]),
                }
            ]
        )
        conn.fetchrow = AsyncMock(return_value=None)
        conn.execute = AsyncMock()

        await store._link_episode_entities(eid, "Alice went to the meeting")

        assert conn.execute.await_count == 2
        gs.upsert_relationship.assert_awaited_once()
        rel = gs.upsert_relationship.call_args[0][0]
        assert rel.predicate == "MENTIONS"
        assert rel.target_id == entity_id

    async def test_link_episode_entities_no_match_skips_graph(self):
        pool, conn = _make_pool()
        gs = _make_graph_store()
        store, _ = _make_store(pool, graph_store=gs)

        eid = uuid4()
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock()

        await store._link_episode_entities(eid, "No names mentioned here")

        conn.execute.assert_not_awaited()
        gs.upsert_relationship.assert_not_awaited()


# ── _promote_event_outcome ────────────────────────────────────────────────────


class TestPromoteEventOutcome:
    def _make_store_with_client(
        self, pool=None, graph_store=None, client_response=None
    ):
        pool, conn = _make_pool()
        fact_id = uuid4()
        conn.fetchrow = AsyncMock(return_value={"id": fact_id})
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock()
        pool.acquire = MagicMock(return_value=_async_ctx(conn))

        store = PostgresMemoryStore.__new__(PostgresMemoryStore)
        store._pool = pool
        store._embedder = MagicMock()
        store._embedder.encode = MagicMock(return_value=[0.1] * 384)
        client = AsyncMock()
        client.complete = AsyncMock(return_value=client_response or "[]")
        store._client = client
        store._graph_store = graph_store
        store._traversal = None
        store._settings = None
        return store, conn, client, fact_id

    async def test_creates_promotes_to_edge(self):
        gs = _make_graph_store()
        event_id = uuid4()
        fact_json = '[{"predicate": "prefers_async", "value": "prefers async communication", "confidence": 0.9}]'
        store, conn, client, fact_id = self._make_store_with_client(
            graph_store=gs, client_response=fact_json
        )

        await store._promote_event_outcome(
            event_id, "signed the contract asynchronously"
        )

        calls = gs.upsert_relationship.call_args_list
        promotes = [c for c in calls if c[0][0].predicate == "PROMOTES_TO"]
        assert len(promotes) == 1
        rel = promotes[0][0][0]
        assert rel.source_id == event_id
        assert rel.source_type == "event"
        assert rel.target_id == fact_id
        assert rel.target_type == "fact"
        assert rel.confidence.value == 0.9

    async def test_no_op_without_client(self):
        gs = _make_graph_store()
        pool, conn = _make_pool()
        store, _ = _make_store(pool, graph_store=gs)
        store._client = None

        await store._promote_event_outcome(uuid4(), "some outcome")

        gs.upsert_relationship.assert_not_awaited()

    async def test_no_op_without_graph_store(self):
        pool, conn = _make_pool()
        store, _, client, _ = self._make_store_with_client(graph_store=None)

        # should not raise
        await store._promote_event_outcome(uuid4(), "some outcome")

        client.complete.assert_not_awaited()

    async def test_swallows_llm_failure(self):
        gs = _make_graph_store()
        pool, conn = _make_pool()
        store, _, client, _ = self._make_store_with_client(graph_store=gs)
        client.complete = AsyncMock(side_effect=RuntimeError("LLM exploded"))

        # should not raise
        await store._promote_event_outcome(uuid4(), "the deal fell through")

        gs.upsert_relationship.assert_not_awaited()

    async def test_empty_extraction_creates_no_edges(self):
        gs = _make_graph_store()
        store, conn, client, _ = self._make_store_with_client(
            graph_store=gs, client_response="[]"
        )

        await store._promote_event_outcome(uuid4(), "nothing memorable happened")

        gs.upsert_relationship.assert_not_awaited()


# ── propose_events PROMOTES_TO wiring ────────────────────────────────────────


async def test_propose_events_fires_promotes_to_when_outcome_set():
    pool, conn = _make_pool()
    gs = _make_graph_store()
    event_id = uuid4()
    conn.fetchrow = AsyncMock(return_value={"id": event_id})
    store, _ = _make_store(pool, graph_store=gs)

    with patch.object(store, "_promote_event_outcome", new_callable=AsyncMock):
        with patch("asyncio.create_task") as mock_task:
            event = Event(
                id=None,
                event_type="meeting",
                title="Signed contract",
                outcome="signed the deal",
            )
            await store.propose_events([event])

            assert mock_task.call_count >= 1


async def test_propose_events_no_promotes_to_when_no_outcome():
    pool, conn = _make_pool()
    gs = _make_graph_store()
    event_id = uuid4()
    conn.fetchrow = AsyncMock(return_value={"id": event_id})
    store, _ = _make_store(pool, graph_store=gs)

    with patch.object(
        store, "_promote_event_outcome", new_callable=AsyncMock
    ) as mock_promote:
        event = Event(
            id=None, event_type="meeting", title="Planning session", outcome=None
        )
        await store.propose_events([event])

        mock_promote.assert_not_awaited()


# ── _write_fact_with_contradiction_check returns UUID ────────────────────────


async def test_write_fact_returns_uuid():
    pool, conn = _make_pool()
    fact_id = uuid4()
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": fact_id})
    pool.acquire = MagicMock(return_value=_async_ctx(conn))

    store = PostgresMemoryStore.__new__(PostgresMemoryStore)
    store._pool = pool
    store._embedder = MagicMock()
    store._embedder.encode = MagicMock(return_value=[0.1] * 384)
    store._client = None
    store._graph_store = None
    store._traversal = None
    store._settings = None

    from ze_memory.types import Fact

    fact = Fact(
        id=None,
        subject_id=None,
        predicate="prefers_tea",
        value="prefers tea",
        object_text="tea",
        confidence=0.9,
    )
    result = await store._write_fact_with_contradiction_check(fact)

    assert result == fact_id


async def test_write_fact_returns_none_on_db_error():
    pool, conn = _make_pool()
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=RuntimeError("DB error"))
    pool.acquire = MagicMock(return_value=_async_ctx(conn))

    store = PostgresMemoryStore.__new__(PostgresMemoryStore)
    store._pool = pool
    store._embedder = MagicMock()
    store._embedder.encode = MagicMock(return_value=[0.1] * 384)
    store._client = None
    store._graph_store = None
    store._traversal = None
    store._settings = None

    from ze_memory.types import Fact

    fact = Fact(
        id=None,
        subject_id=None,
        predicate="mood",
        value="cheerful",
        object_text="cheerful",
        confidence=0.7,
    )
    with pytest.raises(RuntimeError):
        await store._write_fact_with_contradiction_check(fact)


# ── contradiction scoping by (predicate, subject_id) ─────────────────────────


def _make_contradiction_store():
    """Return a store whose connection captures execute() call args."""
    pool = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": uuid4()})
    pool.acquire = MagicMock(return_value=_async_ctx(conn))

    store = PostgresMemoryStore.__new__(PostgresMemoryStore)
    store._pool = pool
    store._embedder = MagicMock()
    store._embedder.encode = MagicMock(return_value=[0.1] * 384)
    store._client = None
    store._graph_store = None
    store._traversal = None
    store._settings = None
    return store, conn


async def test_contradiction_update_scoped_to_predicate_and_subject():
    """The UPDATE must pass exactly (predicate, subject_id) — not a null wildcard."""
    store, conn = _make_contradiction_store()
    subject_id = uuid4()

    from ze_memory.types import Fact

    fact = Fact(
        id=None,
        subject_id=subject_id,
        predicate="preferred_name",
        value="Alice",
        object_text="Alice",
        confidence=0.9,
    )
    await store._write_fact_with_contradiction_check(fact)

    conn.execute.assert_awaited_once()
    _sql, pred_arg, subj_arg = conn.execute.call_args[0]
    assert pred_arg == "preferred_name"
    assert subj_arg == subject_id


async def test_contradiction_different_subjects_use_different_scope():
    """Writing the same predicate for two subjects produces two separate UPDATE scopes."""
    store, conn = _make_contradiction_store()
    subject_a = uuid4()
    subject_b = uuid4()

    from ze_memory.types import Fact

    fact_a = Fact(
        id=None,
        subject_id=subject_a,
        predicate="preferred_name",
        value="Alice",
        object_text="Alice",
        confidence=0.9,
    )
    fact_b = Fact(
        id=None,
        subject_id=subject_b,
        predicate="preferred_name",
        value="Bob",
        object_text="Bob",
        confidence=0.9,
    )

    await store._write_fact_with_contradiction_check(fact_a)
    await store._write_fact_with_contradiction_check(fact_b)

    assert conn.execute.await_count == 2
    first_subj = conn.execute.call_args_list[0][0][2]
    second_subj = conn.execute.call_args_list[1][0][2]
    assert first_subj == subject_a
    assert second_subj == subject_b
    assert first_subj != second_subj


async def test_contradiction_null_subject_scoped_independently():
    """NULL subject_id facts only contradict other NULL-subject facts for the same predicate."""
    store, conn = _make_contradiction_store()

    from ze_memory.types import Fact

    # subject_id=None: global/unattributed fact
    fact = Fact(
        id=None,
        subject_id=None,
        predicate="user_timezone",
        value="UTC",
        object_text="UTC",
        confidence=0.8,
    )
    await store._write_fact_with_contradiction_check(fact)

    conn.execute.assert_awaited_once()
    _sql, pred_arg, subj_arg = conn.execute.call_args[0]
    assert pred_arg == "user_timezone"
    assert subj_arg is None


async def test_persist_facts_contradicts_per_subject():
    """_persist_facts calls _write_fact_with_contradiction_check for each fact independently."""
    store, conn = _make_contradiction_store()
    subject_a = uuid4()
    subject_b = uuid4()

    from ze_memory.types import Fact

    facts = [
        Fact(
            id=None,
            subject_id=subject_a,
            predicate="preferred_name",
            value="Alice",
            object_text="Alice",
            confidence=0.9,
        ),
        Fact(
            id=None,
            subject_id=subject_b,
            predicate="preferred_name",
            value="Bob",
            object_text="Bob",
            confidence=0.9,
        ),
    ]
    await store._persist_facts(facts)

    # Two UPDATE calls, one per subject
    assert conn.execute.await_count == 2
    subjects_seen = {conn.execute.call_args_list[i][0][2] for i in range(2)}
    assert subjects_seen == {subject_a, subject_b}


async def test_write_fact_rejects_unknown_provenance():
    store, conn = _make_contradiction_store()
    conn.fetchrow = AsyncMock(return_value={"id": uuid4()})
    from ze_memory.errors import InvalidFactProvenanceError
    from ze_memory.types import Fact

    fact = Fact(predicate="city", value="Lisbon", provenance="raw")  # type: ignore[arg-type]
    with pytest.raises(InvalidFactProvenanceError):
        await store._write_fact_with_contradiction_check(fact)
    conn.fetchrow.assert_not_awaited()


async def test_write_fact_inserts_doctrine_provenance_and_claim_kind():
    store, conn = _make_contradiction_store()
    fact_id = uuid4()
    conn.fetchrow = AsyncMock(return_value={"id": fact_id})
    from ze_agents.claims import ClaimKind, Provenance
    from ze_memory.types import Fact

    fact = Fact(
        predicate="city",
        value="Lisbon",
        provenance=Provenance.PROMPT_SUPPLIED,
        claim_kind=ClaimKind.FACT,
    )
    result = await store._write_fact_with_contradiction_check(fact)
    assert result == fact_id
    sql = conn.fetchrow.await_args.args[0]
    assert "provenance" in sql
    args = conn.fetchrow.await_args.args
    assert Provenance.PROMPT_SUPPLIED.value in args
    assert ClaimKind.FACT.value in args


async def test_synthesized_without_claim_kind_derives_inference():
    store, conn = _make_contradiction_store()
    conn.fetchrow = AsyncMock(return_value={"id": uuid4()})
    from ze_agents.claims import ClaimKind, Provenance
    from ze_memory.types import Fact

    fact = Fact(
        predicate="insight",
        value="pattern",
        provenance=Provenance.SYNTHESIZED,
        claim_kind=None,
    )
    await store._write_fact_with_contradiction_check(fact)
    assert ClaimKind.INFERENCE.value in conn.fetchrow.await_args.args


def test_fact_from_row_loads_claim_kind_and_provenance():
    from uuid import uuid4

    from ze_agents.claims import ClaimKind, Provenance
    from ze_memory.projection import _fact_from_row

    fact = _fact_from_row(
        {
            "id": uuid4(),
            "subject_id": None,
            "predicate": "city",
            "object_text": None,
            "object_id": None,
            "value": "Lisbon",
            "confidence": 0.9,
            "reviewed": False,
            "contradicted": False,
            "source_episode_id": None,
            "source_refs": "[]",
            "provenance": "synthesized",
            "claim_kind": "inference",
        }
    )
    assert fact.provenance is Provenance.SYNTHESIZED
    assert fact.claim_kind is ClaimKind.INFERENCE
