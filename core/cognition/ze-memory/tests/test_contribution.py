from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_agents.errors import DanglingEvidenceError, UnlicensedClaimKindError
from ze_plugin.contribution import Contribution, EvidenceRef, SourceFunction, TargetFace

from ze_memory.contribution import (
    PerceptionFactSubmit,
    fact_to_contribution,
    signal_to_contribution,
    submit_perception_facts,
)
from ze_memory.retriever import PostgresMemoryStore
from ze_memory.types import Fact, Signal


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


def _make_fact(**kwargs) -> Fact:
    defaults = dict(predicate="city", value="Lisbon", confidence=0.8)
    defaults.update(kwargs)
    return Fact(**defaults)


def test_fact_to_contribution_stamps_perception_fact_envelope():
    subject = uuid4()
    obj = uuid4()
    fact = _make_fact(subject_id=subject, object_id=obj)
    contribution = fact_to_contribution(
        fact,
        provenance=Provenance.SYNTHESIZED,
        target_face=TargetFace.USER,
    )
    assert contribution.claim_kind == ClaimKind.FACT
    assert contribution.provenance == Provenance.SYNTHESIZED
    assert contribution.source_function == SourceFunction.PERCEPTION
    assert contribution.target_face == TargetFace.USER
    assert contribution.content == "city Lisbon"
    assert contribution.entity_ids == [subject, obj]
    assert fact.provenance is Provenance.PROMPT_SUPPLIED


async def test_submit_perception_facts_rejects_unlicensed_before_persist():
    store = MagicMock()
    store._write_fact_with_contradiction_check = AsyncMock(return_value=uuid4())
    store._collision_store = None
    store._nli = None
    fact = _make_fact()
    mistagged = Contribution(
        claim_kind=ClaimKind.INFERENCE,
        provenance=Provenance.SYNTHESIZED,
        confidence=Confidence(value=0.8, decay_profile=DecayProfile.TIME_LINEAR),
        target_face=TargetFace.USER,
        source_function=SourceFunction.PERCEPTION,
        evidence=[],
    )
    with patch(
        "ze_memory.contribution.fact_to_contribution", return_value=mistagged
    ):
        with pytest.raises(UnlicensedClaimKindError):
            await submit_perception_facts(
                store,
                [
                    PerceptionFactSubmit(
                        fact=fact,
                        provenance=Provenance.SYNTHESIZED,
                        target_face=TargetFace.USER,
                        evidence=[],
                    )
                ],
            )
    store._write_fact_with_contradiction_check.assert_not_awaited()


async def test_submit_perception_facts_mixed_license_rejects_before_second_persist():
    store = MagicMock()
    store._write_fact_with_contradiction_check = AsyncMock(return_value=uuid4())
    store._collision_store = None
    store._nli = None
    good = _make_fact(predicate="city", value="Lisbon")
    bad = _make_fact(predicate="job", value="eng")

    def _to_contrib(fact, **kwargs):
        kind = (
            ClaimKind.INFERENCE if fact.predicate == "job" else ClaimKind.FACT
        )
        return Contribution(
            claim_kind=kind,
            provenance=kwargs["provenance"],
            confidence=Confidence(value=0.8, decay_profile=DecayProfile.TIME_LINEAR),
            target_face=kwargs["target_face"],
            source_function=SourceFunction.PERCEPTION,
            evidence=kwargs.get("evidence") or [],
            content=f"{fact.predicate} {fact.value}",
        )

    with patch("ze_memory.contribution.fact_to_contribution", side_effect=_to_contrib):
        with pytest.raises(UnlicensedClaimKindError):
            await submit_perception_facts(
                store,
                [
                    PerceptionFactSubmit(
                        fact=good,
                        provenance=Provenance.SYNTHESIZED,
                        target_face=TargetFace.USER,
                        evidence=[],
                    ),
                    PerceptionFactSubmit(
                        fact=bad,
                        provenance=Provenance.SYNTHESIZED,
                        target_face=TargetFace.USER,
                        evidence=[],
                    ),
                ],
            )
    assert store._write_fact_with_contradiction_check.await_count == 1


async def test_submit_perception_facts_ingestion_evidence_persists():
    store = MagicMock()
    fact_id = uuid4()
    store._write_fact_with_contradiction_check = AsyncMock(return_value=fact_id)
    collision = MagicMock()
    nli = MagicMock()
    store._collision_store = collision
    store._nli = nli
    ingest_id = uuid4()
    fact = _make_fact(source_refs=[ingest_id])
    with patch(
        "ze_memory.contribution.submit_and_detect_collisions",
        new_callable=AsyncMock,
        return_value=fact_id,
    ) as submit:
        await submit_perception_facts(
            store,
            [
                PerceptionFactSubmit(
                    fact=fact,
                    provenance=Provenance.SYNTHESIZED,
                    target_face=TargetFace.WORLD,
                    evidence=[EvidenceRef(kind="ingestion", id=ingest_id)],
                )
            ],
        )
    submit.assert_awaited_once()
    kwargs = submit.await_args.kwargs
    assert kwargs["producer_kind"] == "fact"
    assert kwargs["collision_store"] is collision
    assert kwargs["nli_client"] is nli
    contribution = submit.await_args.args[0]
    assert contribution.claim_kind == ClaimKind.FACT
    assert contribution.source_function == SourceFunction.PERCEPTION
    assert contribution.evidence[0].kind == "ingestion"


async def test_submit_perception_facts_dangling_fact_evidence_fails():
    store = MagicMock()
    store._write_fact_with_contradiction_check = AsyncMock(return_value=uuid4())
    store._collision_store = None
    store._nli = None
    with pytest.raises(DanglingEvidenceError):
        await submit_perception_facts(
            store,
            [
                PerceptionFactSubmit(
                    fact=_make_fact(),
                    provenance=Provenance.SYNTHESIZED,
                    target_face=TargetFace.USER,
                    evidence=[EvidenceRef(kind="fact", id=uuid4())],
                )
            ],
        )
    store._write_fact_with_contradiction_check.assert_not_awaited()
