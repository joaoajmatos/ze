from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from ze_agents.claims import ClaimKind, DecayProfile, Provenance
from ze_agents.errors import UnlicensedClaimKindError
from ze_plugin.contribution import SourceFunction, TargetFace

from ze_correlation.engine import CorrelationEngine
from ze_correlation.types import EvidenceRef, Hypothesis


def _make_engine() -> tuple[CorrelationEngine, AsyncMock]:
    memory_store = AsyncMock()
    memory_store.get_facts_by_ids = AsyncMock(return_value=[object()])
    memory_store.get_episodes_by_ids = AsyncMock(return_value=[object()])
    memory_store.get_signals_by_ids = AsyncMock(return_value=[object()])
    hypothesis_store = AsyncMock()
    hypothesis_store.save = AsyncMock()

    engine = CorrelationEngine(
        memory_store=memory_store,
        relevance_model=AsyncMock(),
        llm_client=AsyncMock(),
        hypothesis_store=hypothesis_store,
        settings={},
    )
    return engine, hypothesis_store


def _make_hypothesis(**overrides) -> Hypothesis:
    defaults = dict(
        id=uuid4(),
        summary="A pattern was noticed.",
        narrative="Reasoning goes here.",
        relation="pattern",
        confidence=0.6,
        relevance=0.7,
        evidence=[
            EvidenceRef(
                kind="fact",
                id=uuid4(),
                label="some fact",
                external_ref=None,
                origin=Provenance.GRAPH_RECALL,
                retrieved_at=datetime.now(timezone.utc),
            ),
            EvidenceRef(
                kind="episode",
                id=uuid4(),
                label="some episode",
                external_ref=None,
                origin=Provenance.GRAPH_RECALL,
                retrieved_at=datetime.now(timezone.utc),
            ),
        ],
        entities=[],
        created_at=datetime.now(timezone.utc),
        claim_kind=ClaimKind.SUSPICION,
    )
    defaults.update(overrides)
    return Hypothesis(**defaults)


async def test_fact_hypothesis_rejected_before_save():
    engine, hypothesis_store = _make_engine()
    hypothesis = _make_hypothesis(claim_kind=ClaimKind.FACT)

    with pytest.raises(UnlicensedClaimKindError):
        await engine._save_hypothesis_via_seam(hypothesis)

    hypothesis_store.save.assert_not_awaited()


async def test_suspicion_hypothesis_persists_exactly_as_before():
    engine, hypothesis_store = _make_engine()
    hypothesis = _make_hypothesis(claim_kind=ClaimKind.SUSPICION, confidence=0.42)

    await engine._save_hypothesis_via_seam(hypothesis)

    hypothesis_store.save.assert_awaited_once_with(hypothesis)


async def test_contribution_uses_time_linear_decay_and_self_face():
    from ze_correlation import engine as engine_module

    captured = {}
    original = engine_module.validate_and_submit

    async def _spy(contribution, write, **checkers):
        captured["contribution"] = contribution
        return await original(contribution, write, **checkers)

    engine, _ = _make_engine()
    hypothesis = _make_hypothesis()

    import unittest.mock as mock

    with mock.patch("ze_correlation.engine.validate_and_submit", new=_spy):
        await engine._save_hypothesis_via_seam(hypothesis)

    contribution = captured["contribution"]
    assert contribution.confidence.decay_profile == DecayProfile.TIME_LINEAR
    assert contribution.confidence.value == hypothesis.confidence
    assert contribution.target_face == TargetFace.SELF
    assert contribution.source_function == SourceFunction.REFLECTION
