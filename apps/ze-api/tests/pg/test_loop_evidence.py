import hashlib
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from ze_memory.retriever import PostgresMemoryStore
from ze_plugin.contribution import EvidenceRef
from ze_priority.push_bar import PushBar
from ze_worldstate.admission import LoopInflow
from ze_worldstate.bootstrap import LoopPushSettings
from ze_worldstate.decision import CommitDecision
from ze_worldstate.lifecycle import LoopLifecycle
from ze_worldstate.rest import _fetch_evidence_summaries
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.surfacing import LoopSurfacer
from ze_worldstate.types import LoopState

from tests.pg._builders import link_evidence, make_episode, make_loop, utcnow

pytestmark = pytest.mark.pg


class _TitleEmbedder:
    """Same title -> same vector; different titles -> orthogonal."""

    def encode_passage(self, text):
        digest = hashlib.sha256(text.encode()).digest()
        vec = [0.0] * 32
        vec[digest[0] % 32] = 1.0
        return vec

    encode_query = encode_passage


def _graph():
    graph = MagicMock()
    graph.list_relationships = AsyncMock(return_value=[])
    return graph


def _inflow(pool):
    return LoopInflow(
        lifecycle=LoopLifecycle(pool, memory_store=PostgresMemoryStore(pool, None, None)),
        loop_store=PostgresLoopStore(pool),
        graph_store=_graph(),
        entity_resolver=AsyncMock(return_value=[]),
        llm_client=AsyncMock(),
        embedder=_TitleEmbedder(),
    )


async def _commit(pool, text, inflow, refs, *, kind="create_suspected", title="Renew passport"):
    return await _inflow(pool).commit(
        CommitDecision(kind, "test", title=title), text=text, inflow=inflow, evidence=refs
    )


async def test_suspected_loop_stores_its_episode_evidence(pg_pool):
    episode_id = await make_episode(pg_pool)
    ref = EvidenceRef(kind="episode", id=episode_id)

    result = await _commit(pg_pool, "maybe renew my passport", "email", [ref])

    [loop] = result.loops
    assert result.outcome == "created" and loop.state is LoopState.SUSPECTED
    assert await PostgresLoopStore(pg_pool).list_evidence(loop.id) == [ref]


async def test_declared_loop_stores_evidence(pg_pool):
    episode_id = await make_episode(pg_pool)
    ref = EvidenceRef(kind="episode", id=episode_id)

    result = await _commit(
        pg_pool, "I need to renew my passport", "conversation", [ref], kind="create_declared"
    )

    [loop] = result.loops
    assert loop.state is LoopState.ACTIVE
    assert loop.provenance == "user_declared"
    assert await PostgresLoopStore(pg_pool).list_evidence(loop.id) == [ref]


async def test_second_declaration_corroborates_instead_of_duplicating(pg_pool):
    store = PostgresLoopStore(pg_pool)
    first = EvidenceRef(kind="episode", id=await make_episode(pg_pool))
    second = EvidenceRef(kind="episode", id=await make_episode(pg_pool, prompt="again, the passport"))

    declared = dict(kind="create_declared")
    [loop] = (await _commit(pg_pool, "I need to renew my passport", "conversation", [first], **declared)).loops
    async with pg_pool.acquire() as conn:
        await conn.execute("UPDATE open_loops SET drift_deadline = now() + interval '1 day' WHERE id = $1", loop.id)
    result = await _commit(pg_pool, "I need to renew my passport", "conversation", [second], **declared)

    [again] = result.loops
    assert result.outcome == "matched" and again.id == loop.id
    assert len(await store.list()) == 1
    assert await store.count_evidence_links(loop.id) == 2
    assert (await store.get(loop.id)).drift_deadline >= utcnow() + timedelta(days=7) - timedelta(minutes=1)
    assert (await store.get(loop.id)).state is LoopState.ACTIVE


async def test_dropped_loop_replays_same_evidence_but_new_evidence_resuspects(pg_pool):
    store = PostgresLoopStore(pg_pool)
    old = EvidenceRef(kind="episode", id=await make_episode(pg_pool))
    [loop] = (await _commit(pg_pool, "maybe renew my passport", "email", [old])).loops
    await LoopLifecycle(pg_pool).drop(loop.id)

    replay = await _commit(pg_pool, "maybe renew my passport", "email", [old])
    assert (replay.outcome, replay.loops) == ("dismissed", ())
    assert len(await store.list()) == 1

    new = EvidenceRef(kind="episode", id=await make_episode(pg_pool, prompt="renew passport soon"))
    [fresh] = (await _commit(pg_pool, "maybe renew my passport", "email", [new])).loops
    assert fresh.id != loop.id and fresh.state is LoopState.SUSPECTED


async def test_messenger_episode_summary_includes_the_email_body(pg_pool):
    episode_id = await make_episode(
        pg_pool, agent="messenger", prompt="Passport renewal", response="Please send the signed form by Friday"
    )
    loop = await make_loop(pg_pool)
    store = PostgresLoopStore(pg_pool)
    await link_evidence(pg_pool, loop.id, "episode", episode_id)

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
    relevance = MagicMock()
    relevance.build = AsyncMock(return_value=object())
    relevance.score = MagicMock(return_value=SimpleNamespace(value=1.0, contributions=[]))
    return LoopSurfacer(
        loop_store=store,
        graph_store=MagicMock(),
        pool=pool,
        relevance_model=relevance,
        notifier=MagicMock(),
        settings=LoopPushSettings(),
    )


def _bar(nli):
    return PushBar(
        embedder=None,
        nli=nli,
        history=SimpleNamespace(recent_discretionary_bodies=AsyncMock(return_value=[])),
        mentions=SimpleNamespace(mentioned_inline_within=AsyncMock(return_value=False)),
    )


async def test_push_bar_grounds_the_title_against_real_evidence(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(
        pg_pool,
        state=LoopState.DRIFTING,
        confidence=0.9,
        rationale="No corroborating evidence before the implied window elapsed.",
    )
    episode_id = await make_episode(pg_pool)
    await link_evidence(pg_pool, loop.id, "episode", episode_id)
    surfacer = _surfacer(pg_pool, store)
    [candidate] = [c for c in await surfacer.candidates() if c.source_id == loop.id]
    thresholds = surfacer.thresholds

    [grounded] = await _bar(_Nli(loop.title)).screen([candidate], thresholds)
    [ungrounded] = await _bar(_Nli("something else entirely")).screen(
        [candidate], thresholds
    )

    assert grounded.passed is True
    assert (ungrounded.passed, ungrounded.reason) == (False, "ungrounded")
