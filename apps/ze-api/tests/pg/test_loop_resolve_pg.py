"""199 US4: "that's done" closes a loop nobody confirmed, and links the evidence."""

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from structlog.testing import capture_logs
from ze_memory.retriever import PostgresMemoryStore
from ze_plugin.contribution import EvidenceRef
from ze_worldstate.admission import LoopInflow
from ze_worldstate.errors import InvalidLoopTransitionError, LoopNotFoundError
from ze_worldstate.extraction import propose_loop_candidates
from ze_worldstate.loop_judge import LoopGateDecision
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopAdmission, LoopState

from tests.pg._builders import make_episode, make_loop

pytestmark = pytest.mark.pg


class _TitleEmbedder:
    """Same title -> same vector; different titles -> orthogonal."""

    def encode_passage(self, text):
        digest = hashlib.sha256(text.encode()).digest()
        vec = [0.0] * 32
        vec[digest[0] % 32] = 1.0
        return vec

    encode_query = encode_passage


class _Llm:
    def __init__(self, **payload):
        self._payload = json.dumps(payload)

    async def complete(self, *args, **kwargs):
        return self._payload


_CREATE = _Llm(is_loop=True, title="Renew passport", explicit_declaration=False)
_RESOLVE = _Llm(is_loop=False, resolves_existing=True, title="Renew passport")


def _graph():
    graph = MagicMock()
    graph.list_relationships = AsyncMock(return_value=[])
    return graph


async def _propose(pool, text, provenance, refs, llm, *, admission=None):
    return await propose_loop_candidates(
        text,
        provenance,
        refs,
        llm,
        _TitleEmbedder(),
        PostgresLoopStore(pool),
        AsyncMock(return_value=[]),
        graph_store=_graph(),
        memory_store=PostgresMemoryStore(pool, None, None),
        admission=admission,
    )


def _resolve_admission() -> LoopAdmission:
    return LoopAdmission(decision=LoopGateDecision("resolve", "test"))


async def _episode_ref(pool, prompt="renew passport"):
    return EvidenceRef(kind="episode", id=await make_episode(pool, prompt=prompt))


async def _dismissed_fingerprint(pool, loop_id):
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT dismissed_evidence_fingerprint FROM open_loops WHERE id = $1",
            loop_id,
        )


async def test_resolve_closes_a_suspected_loop_and_links_the_evidence(pg_pool):
    store = PostgresLoopStore(pg_pool)
    origin = await _episode_ref(pg_pool)
    [loop] = await _propose(pg_pool, "maybe renew my passport", "email", [origin], _CREATE)
    assert loop.state is LoopState.SUSPECTED
    resolving = await _episode_ref(pg_pool, "I renewed the passport")

    await _propose(pg_pool, "I renewed the passport", "email", [resolving], _RESOLVE)

    closed = await store.get(loop.id)
    assert closed.state is LoopState.CLOSED
    assert closed.closed_at is not None
    assert resolving in await store.list_evidence(loop.id)
    assert await _dismissed_fingerprint(pg_pool, loop.id) is None


@pytest.mark.parametrize(
    ("provenance", "has_evidence"),
    [("conversation", True), ("email", True), ("ingestion", True), ("calendar", False)],
)
async def test_system_one_resolve_closes_a_suspected_loop(
    pg_pool, provenance, has_evidence
):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3, title="Renew passport")
    refs = [await _episode_ref(pg_pool, "I renewed the passport")] if has_evidence else []

    await _propose(
        pg_pool,
        "I renewed the passport",
        provenance,
        refs,
        _RESOLVE,
        admission=_resolve_admission(),
    )

    closed = await store.get(loop.id)
    assert closed.state is LoopState.CLOSED
    assert await store.list_evidence(loop.id) == refs
    assert await _dismissed_fingerprint(pg_pool, loop.id) is None


@pytest.mark.parametrize("state", [LoopState.ACTIVE, LoopState.DRIFTING])
async def test_resolve_closes_active_and_drifting_loops_with_evidence(pg_pool, state):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=state, title="Renew passport")
    ref = await _episode_ref(pg_pool, "I renewed the passport")

    await _propose(pg_pool, "I renewed the passport", "email", [ref], _RESOLVE)

    assert (await store.get(loop.id)).state is LoopState.CLOSED
    assert await store.list_evidence(loop.id) == [ref]
    assert await _dismissed_fingerprint(pg_pool, loop.id) is None


async def test_generic_transition_still_refuses_suspected_to_closed(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)

    with pytest.raises(InvalidLoopTransitionError):
        await store.transition(loop.id, "closed")


async def test_resolve_on_a_dropped_loop_returns_none_and_changes_nothing(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.DROPPED, confidence=0.3)
    ref = await _episode_ref(pg_pool)

    assert await store.resolve(loop.id, [ref]) is None

    after = await store.get(loop.id)
    assert after.state is LoopState.DROPPED
    assert after.closed_at is None
    assert await store.list_evidence(loop.id) == []


async def test_resolve_raises_for_an_unknown_loop(pg_pool):
    with pytest.raises(LoopNotFoundError):
        await PostgresLoopStore(pg_pool).resolve(uuid4(), [])


async def test_commit_for_a_resolve_admission_logs_no_extraction_failure(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3, title="Renew passport")
    ref = await _episode_ref(pg_pool, "I renewed the passport")
    inflow = LoopInflow(
        loop_store=store,
        graph_store=_graph(),
        entity_resolver=AsyncMock(return_value=[]),
        llm_client=_RESOLVE,
        embedder=_TitleEmbedder(),
        memory_store=PostgresMemoryStore(pg_pool, None, None),
    )

    with capture_logs() as logs:
        closed = await inflow.commit_for(
            "I renewed the passport", "email", _resolve_admission()
        )([ref])

    assert [entry for entry in logs if entry["event"] == "loop_extraction_failed"] == []
    [transitioned] = [e for e in logs if e["event"] == "open_loop_transitioned"]
    assert transitioned["via"] == "resolve"
    assert transitioned["from_state"] == "suspected" and transitioned["to_state"] == "closed"
    assert [c.id for c in closed] == [loop.id]
    assert (await store.get(loop.id)).state is LoopState.CLOSED
