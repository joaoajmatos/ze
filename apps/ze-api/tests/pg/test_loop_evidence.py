import hashlib
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from ze_memory.retriever import PostgresMemoryStore
from ze_plugin.contribution import EvidenceRef
from ze_worldstate import review
from ze_worldstate.extraction import propose_loop_candidates
from ze_worldstate.rest import _fetch_evidence_summaries
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.surfacing import LoopSurfacer
from ze_worldstate.types import LoopState

from tests.pg._builders import make_episode, make_loop, utcnow

pytestmark = pytest.mark.pg


class _TitleEmbedder:
    """Same title -> same vector; different titles -> orthogonal."""

    def encode(self, text):
        digest = hashlib.sha256(text.encode()).digest()
        vec = [0.0] * 32
        vec[digest[0] % 32] = 1.0
        return vec


class _Llm:
    def __init__(self, title="Renew passport", explicit=False):
        self._payload = json.dumps(
            {"is_loop": True, "title": title, "explicit_declaration": explicit}
        )

    async def complete(self, *args, **kwargs):
        return self._payload


def _graph():
    graph = MagicMock()
    graph.list_relationships = AsyncMock(return_value=[])
    return graph


async def _propose(
    pool, text, provenance, refs, *, explicit=False, title="Renew passport"
):
    return await propose_loop_candidates(
        text,
        provenance,
        refs,
        _Llm(title, explicit),
        _TitleEmbedder(),
        PostgresLoopStore(pool),
        AsyncMock(return_value=[]),
        graph_store=_graph(),
        memory_store=PostgresMemoryStore(pool, None, None),
    )


async def test_suspected_loop_stores_its_episode_evidence(pg_pool):
    episode_id = await make_episode(pg_pool)
    ref = EvidenceRef(kind="episode", id=episode_id)

    [loop] = await _propose(pg_pool, "maybe renew my passport", "email", [ref])

    assert loop.state is LoopState.SUSPECTED
    assert await PostgresLoopStore(pg_pool).list_evidence(loop.id) == [ref]


async def test_declared_loop_stores_evidence(pg_pool):
    episode_id = await make_episode(pg_pool)
    ref = EvidenceRef(kind="episode", id=episode_id)

    [loop] = await _propose(
        pg_pool, "I need to renew my passport", "user_declared", [ref]
    )

    assert loop.state is LoopState.ACTIVE
    assert await PostgresLoopStore(pg_pool).list_evidence(loop.id) == [ref]


async def test_second_declaration_corroborates_instead_of_duplicating(pg_pool):
    store = PostgresLoopStore(pg_pool)
    first = EvidenceRef(kind="episode", id=await make_episode(pg_pool))
    second = EvidenceRef(
        kind="episode", id=await make_episode(pg_pool, prompt="again, the passport")
    )

    [loop] = await _propose(
        pg_pool, "I need to renew my passport", "user_declared", [first]
    )
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE open_loops SET drift_deadline = now() + interval '1 day' WHERE id = $1",
            loop.id,
        )
    [again] = await _propose(
        pg_pool, "I need to renew my passport", "user_declared", [second]
    )

    assert again.id == loop.id
    assert len(await store.list()) == 1
    assert await store.count_evidence_links(loop.id) == 2
    assert (await store.get(loop.id)).drift_deadline >= utcnow() + timedelta(
        days=7
    ) - timedelta(minutes=1)
    assert (await store.get(loop.id)).state is LoopState.ACTIVE


async def test_dropped_loop_replays_same_evidence_but_new_evidence_resuspects(pg_pool):
    store = PostgresLoopStore(pg_pool)
    old = EvidenceRef(kind="episode", id=await make_episode(pg_pool))
    [loop] = await _propose(pg_pool, "maybe renew my passport", "email", [old])
    await review.drop_loop(store, loop.id)

    assert await _propose(pg_pool, "maybe renew my passport", "email", [old]) == []
    assert len(await store.list()) == 1

    new = EvidenceRef(
        kind="episode", id=await make_episode(pg_pool, prompt="renew passport soon")
    )
    [fresh] = await _propose(pg_pool, "maybe renew my passport", "email", [new])
    assert fresh.id != loop.id and fresh.state is LoopState.SUSPECTED


async def test_messenger_episode_summary_includes_the_email_body(pg_pool):
    episode_id = await make_episode(
        pg_pool,
        agent="messenger",
        prompt="Passport renewal",
        response="Please send the signed form by Friday",
    )
    loop = await make_loop(pg_pool)
    store = PostgresLoopStore(pg_pool)
    await store.link_evidence(loop.id, "episode", episode_id)

    [summary] = await _fetch_evidence_summaries(pg_pool, store, loop.id)

    assert "Passport renewal" in summary["summary"]
    assert "signed form by Friday" in summary["summary"]


class _Nli:
    """Entails the title (0.9) but not the absence rationale (0.1)."""

    def __init__(self, title):
        self._title = title

    async def scores(self, pairs):
        return [0.9 if hyp == self._title else 0.1 for _label, hyp in pairs]

    def grounding_score(self, summary, labels, scores=None):
        return max(scores)


def _surfacer(pool, store):
    push_log = AsyncMock()
    push_log.list_recent_payloads = AsyncMock(return_value=[])
    push_log.was_sent_within_hours = AsyncMock(return_value=False)
    relevance = MagicMock()
    relevance.build = AsyncMock(return_value=object())
    relevance.score = MagicMock(
        return_value=SimpleNamespace(value=1.0, contributions=[])
    )
    return LoopSurfacer(
        store,
        MagicMock(),
        push_log,
        pool=pool,
        relevance_model=relevance,
        embedder=None,
    )


async def test_push_bar_grounds_the_title_against_real_evidence(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(pg_pool, state=LoopState.DRIFTING, confidence=0.9)
    episode_id = await make_episode(pg_pool)
    await store.link_evidence(loop.id, "episode", episode_id)
    rationale = "No corroborating evidence before the implied window elapsed."
    surfacer = _surfacer(pg_pool, store)

    assert (
        await surfacer.passes_push_bar(
            loop, rationale, nli_client=_Nli(loop.title), check_budget=False
        )
        is True
    )
    assert (
        await surfacer.passes_push_bar(
            loop,
            rationale,
            nli_client=_Nli("something else entirely"),
            check_budget=False,
        )
        is False
    )
