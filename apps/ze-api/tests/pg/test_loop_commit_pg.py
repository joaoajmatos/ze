"""LoopInflow.commit against real events (spec US3, FR-013, SC-005)."""

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from ze_memory.retriever import PostgresMemoryStore
from ze_plugin.contribution import EvidenceRef
from ze_worldstate.admission import LoopInflow
from ze_worldstate.decision import CommitDecision
from ze_worldstate.jobs.drift_sweep import DriftSweepJob
from ze_worldstate.jobs.stale_suspicion import StaleSuspicionJob
from ze_worldstate.lifecycle import LoopLifecycle
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopSourceRole, LoopState, SourceKey

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


class _Writer:
    """The fake title writer: names every loop the same way, whatever the text."""

    def __init__(self, title="Renew passport"):
        self._payload = json.dumps({"title": title})

    async def complete(self, *args, **kwargs):
        return self._payload


def _inflow(pool, llm=None):
    lifecycle = LoopLifecycle(pool, memory_store=PostgresMemoryStore(pool, None, None))
    graph = MagicMock()
    graph.list_relationships = AsyncMock(return_value=[])
    return LoopInflow(
        lifecycle=lifecycle,
        loop_store=PostgresLoopStore(pool),
        graph_store=graph,
        entity_resolver=AsyncMock(return_value=[]),
        llm_client=llm or _Writer(),
        embedder=_TitleEmbedder(),
        system_one_client=None,
    )


async def _ref(pool, prompt="renew passport"):
    return EvidenceRef(kind="episode", id=await make_episode(pool, prompt=prompt))


async def _loops(pool, title=None):
    loops = await PostgresLoopStore(pool).list()
    return [loop for loop in loops if title is None or loop.title == title]


# ── each decision ────────────────────────────────────────────────────────────


async def test_hold_writes_nothing(pg_pool):
    result = await _inflow(pg_pool).commit(
        CommitDecision("hold", "not_open_concern"), text="thanks", inflow="email"
    )
    assert result.outcome == "held"
    assert await _loops(pg_pool) == []


async def test_a_suspected_decision_creates_one_loop_with_evidence_and_an_origin_source(
    pg_pool,
):
    store = PostgresLoopStore(pg_pool)
    ref = await _ref(pg_pool)

    result = await _inflow(pg_pool).commit(
        CommitDecision("create_suspected", "implied"),
        text="Daniel is still waiting on my answer",
        inflow="conversation",
        evidence=[ref],
        source=SourceKey("conversation", "thread-1"),
    )

    assert result.outcome == "created"
    [loop] = await _loops(pg_pool)
    assert loop.state is LoopState.SUSPECTED
    assert loop.confidence == pytest.approx(0.3)
    assert loop.provenance == "conversation"
    assert await store.list_evidence(loop.id) == [ref]
    [origin] = await store.list_sources(loop.id)
    assert origin.role is LoopSourceRole.ORIGIN
    assert origin.key == SourceKey("conversation", "thread-1")


async def test_a_declared_decision_creates_an_active_user_declared_loop(pg_pool):
    ref = await _ref(pg_pool)

    result = await _inflow(pg_pool).commit(
        CommitDecision("create_declared", "explicit", window_days=3),
        text="I need to renew my passport",
        inflow="conversation",
        evidence=[ref],
    )

    [loop] = result.loops
    assert loop.state is LoopState.ACTIVE
    assert loop.confidence == pytest.approx(0.9)
    assert loop.provenance == "user_declared"
    assert loop.drift_deadline is not None


async def test_a_resolve_decision_closes_the_matching_loop(pg_pool):
    inflow = _inflow(pg_pool)
    [loop] = (
        await inflow.commit(
            CommitDecision("create_suspected", "implied"),
            text="renew passport",
            inflow="email",
            evidence=[await _ref(pg_pool)],
        )
    ).loops

    result = await inflow.commit(
        CommitDecision("resolve", "resolves"),
        text="I renewed the passport",
        inflow="email",
        evidence=[await _ref(pg_pool, "renewed")],
    )

    assert result.outcome == "resolved"
    assert (await PostgresLoopStore(pg_pool).get(loop.id)).state is LoopState.CLOSED


async def test_a_fallback_decision_runs_the_109_gate(pg_pool):
    class Gate:
        async def complete(self, messages, **kw):
            if "relevance gate" in kw.get("system", ""):
                return json.dumps({"is_loop": True, "title": "Renew passport"})
            raise AssertionError("the gate's title needs no writer")

    result = await _inflow(pg_pool, Gate()).commit(
        CommitDecision("fallback", "disabled"),
        text="maybe renew my passport",
        inflow="email",
        evidence=[await _ref(pg_pool)],
    )
    assert result.outcome == "created"
    assert len(await _loops(pg_pool)) == 1


async def test_a_second_text_about_the_same_concern_matches_instead_of_duplicating(
    pg_pool,
):
    inflow = _inflow(pg_pool)
    for _ in range(2):
        await inflow.commit(
            CommitDecision("create_suspected", "implied"),
            text="renew passport",
            inflow="email",
            evidence=[await _ref(pg_pool)],
        )
    [loop] = await _loops(pg_pool)
    assert await PostgresLoopStore(pg_pool).count_evidence_links(loop.id) == 2


# ── FR-013: a dangling reference is an error, not a loop ─────────────────────


@pytest.mark.parametrize("kind", ["create_declared", "create_suspected"])
async def test_evidence_that_does_not_exist_ends_as_an_error_with_no_row(pg_pool, kind):
    ghost = EvidenceRef(kind="episode", id=uuid4())

    result = await _inflow(pg_pool).commit(
        CommitDecision(kind, "test"),
        text="I need to renew my passport",
        inflow="conversation",
        evidence=[ghost],
    )

    assert result.outcome == "error"
    assert await _loops(pg_pool) == []


# ── SC-005: a dismissed loop does not come back ──────────────────────────────

_DAYS = 30


async def _age_one_day(pool):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE open_loops SET created_at = created_at - interval '1 day',"
            " drift_deadline = drift_deadline - interval '1 day'"
        )


async def test_dropped_and_expired_loops_with_evidence_stay_gone_for_thirty_days(
    pg_pool,
):
    store = PostgresLoopStore(pg_pool)
    lifecycle = LoopLifecycle(pg_pool, memory_store=PostgresMemoryStore(pg_pool, None, None))
    stale = StaleSuspicionJob(store, lifecycle)
    drift = DriftSweepJob(store, lifecycle)

    texts = {
        "Renew the passport": await _ref(pg_pool, "renew the passport"),
        "Reply to Ana about the budget": await _ref(pg_pool, "reply to ana"),
        "Book the dentist": await _ref(pg_pool, "book the dentist"),
    }

    async def replay(title, refs):
        return await _inflow(pg_pool, _Writer(title)).commit(
            CommitDecision("create_suspected", "implied"),
            text=title,
            inflow="email",
            evidence=refs,
        )

    for title, ref in texts.items():
        await replay(title, [ref])
    # A suspected loop with no evidence cannot be created through the seam; seed one.
    plants = await make_loop(
        pg_pool, title="Water the plants", state=LoopState.SUSPECTED, confidence=0.3,
        provenance="email",
    )

    [dropped] = await _loops(pg_pool, "Renew the passport")
    await lifecycle.drop(dropped.id)

    for _ in range(_DAYS):
        await _age_one_day(pg_pool)
        await stale.run()
        await drift.run()
        for title, ref in texts.items():
            assert (await replay(title, [ref])).outcome in {"matched", "dismissed"}

    for title in texts:
        loops = await _loops(pg_pool, title)
        assert [loop.state for loop in loops] == [LoopState.DROPPED], title

    # Expiry with no evidence writes a NULL fingerprint, so it blocks nothing: the same
    # concern with new evidence is created again.
    expired = await store.get(plants.id)
    assert expired.state is LoopState.DROPPED
    assert expired.dismissed_evidence_fingerprint is None
    again = await replay("Water the plants", [await _ref(pg_pool, "water the plants")])
    assert again.outcome == "created"
