from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_plugin.contribution import Contribution, SourceFunction, TargetFace

from ze_memory.contribution import signal_to_contribution
from ze_memory.retriever import PostgresMemoryStore
from ze_memory.types import Signal


def _make_signal(**kwargs) -> Signal:
    defaults = dict(
        id=uuid4(),
        source="news",
        external_ref="https://example.com/article/1",
        title="Anthropic releases new model",
        summary="Anthropic has released a new AI model.",
        occurred_at=datetime(2026, 6, 17, tzinfo=timezone.utc),
        claim_kind=ClaimKind.FACT,
        confidence=0.9,
        provenance=Provenance.LIVE_SEARCH,
        magnitude=0.4,
    )
    defaults.update(kwargs)
    return Signal(**defaults)


# ── signal_to_contribution round-trip ──────────────────────────────────────────


def test_signal_to_contribution_round_trips():
    signal = _make_signal()

    contribution = signal_to_contribution(signal)

    assert contribution.claim_kind == ClaimKind.FACT
    assert contribution.provenance == Provenance.LIVE_SEARCH
    assert contribution.confidence.value == signal.confidence
    assert contribution.confidence.decay_profile == DecayProfile.TIME_LINEAR
    assert contribution.source_function == SourceFunction.PERCEPTION
    assert contribution.target_face == TargetFace.WORLD
    assert contribution.evidence == []


def test_signal_magnitude_stays_distinct_from_confidence():
    signal = _make_signal(confidence=0.9, magnitude=0.4)

    contribution = signal_to_contribution(signal)

    assert signal.magnitude != contribution.confidence.value
    assert contribution.confidence.value == 0.9


# ── ingest_signal real write-path rejection (Edge Case 1) ──────────────────────


class _async_ctx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_):
        pass


def _make_store() -> tuple[PostgresMemoryStore, AsyncMock]:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[None, {"id": uuid4()}])
    conn.execute = AsyncMock()
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_async_ctx(conn))

    store = PostgresMemoryStore.__new__(PostgresMemoryStore)
    store._pool = pool
    store._embedder = None
    store._client = None
    store._graph_store = None
    store._traversal = None
    store._settings = None
    return store, conn


async def test_ingest_signal_rejects_malformed_claim_kind_before_insert():
    store, conn = _make_store()
    signal = _make_signal()
    mistagged = Contribution(
        claim_kind=ClaimKind.INFERENCE,
        provenance=Provenance.LIVE_SEARCH,
        confidence=Confidence(value=0.9, decay_profile=DecayProfile.TIME_LINEAR),
        target_face=TargetFace.WORLD,
        source_function=SourceFunction.PERCEPTION,
        evidence=[],
    )

    with patch("ze_memory.retriever.signal_to_contribution", return_value=mistagged):
        result = await store.ingest_signal(signal)

    assert result is None
    insert_calls = [
        call
        for call in conn.fetchrow.await_args_list
        if "INSERT INTO memory_signals" in call.args[0]
    ]
    assert insert_calls == []
