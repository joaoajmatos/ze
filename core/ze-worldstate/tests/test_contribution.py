from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_agents.errors import UnlicensedClaimKindError
from ze_plugin.contribution import Contribution, SourceFunction, TargetFace

from ze_worldstate.contribution import loop_to_contribution
from ze_worldstate.extraction import propose_loop_candidates
from ze_worldstate.types import EvidenceRef, LoopClaimKind, LoopProvenance, LoopState, OpenLoop


def _make_loop(**kwargs) -> OpenLoop:
    defaults = dict(
        title="Renew passport",
        claim_kind=LoopClaimKind.SUSPICION,
        provenance=LoopProvenance.CONVERSATION,
        confidence=0.3,
        state=LoopState.SUSPECTED,
    )
    defaults.update(kwargs)
    return OpenLoop(**defaults)


# ── loop_to_contribution round-trip ────────────────────────────────────────────


def test_loop_to_contribution_preserves_claim_kind_and_confidence():
    loop = _make_loop(claim_kind=LoopClaimKind.PRIORITY, confidence=0.9)

    contribution = loop_to_contribution(loop)

    assert contribution.claim_kind == LoopClaimKind.PRIORITY
    assert contribution.confidence.value == 0.9
    assert contribution.confidence.decay_profile == DecayProfile.TIME_LINEAR
    assert contribution.source_function == SourceFunction.EXECUTIVE
    assert contribution.target_face == TargetFace.ACTIVE_CONCERNS


def test_loop_to_contribution_maps_inflow_provenance_to_epistemic():
    assert (
        loop_to_contribution(_make_loop(provenance=LoopProvenance.USER_DECLARED)).provenance
        == Provenance.PROMPT_SUPPLIED
    )
    assert (
        loop_to_contribution(_make_loop(provenance=LoopProvenance.CONVERSATION)).provenance
        == Provenance.SYNTHESIZED
    )
    assert (
        loop_to_contribution(_make_loop(provenance=LoopProvenance.INGESTION)).provenance
        == Provenance.SYNTHESIZED
    )


def test_loop_to_contribution_carries_evidence_through():
    ref = EvidenceRef(evidence_type="fact", evidence_id=uuid4())
    from ze_plugin.contribution import EvidenceRef as ContributionEvidenceRef

    contribution_evidence = [
        ContributionEvidenceRef(kind=ref.evidence_type, id=ref.evidence_id)
    ]

    contribution = loop_to_contribution(_make_loop(), evidence=contribution_evidence)

    assert contribution.evidence == contribution_evidence


# ── extraction.py real write-path rejection (Edge Case 1) ──────────────────────


def _llm(response: dict) -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(return_value=json.dumps(response))
    return client


async def test_declared_loop_rejects_malformed_claim_kind_before_create():
    llm = AsyncMock()
    loop_store = AsyncMock()
    loop_store.create = AsyncMock(side_effect=lambda loop: setattr(loop, "id", uuid4()) or loop)
    embedder = AsyncMock()
    entity_resolver = AsyncMock(return_value=[])

    # Simulates a loop contribution mistagged with a source_function whose license
    # doesn't cover PRIORITY (a real OpenLoop claim_kind) — proving the general
    # licensing check applies to loop-shaped contributions the same way it does
    # to reflection's, per Edge Case 1.
    mistagged = Contribution(
        claim_kind=ClaimKind.PRIORITY,
        provenance=Provenance.PROMPT_SUPPLIED,
        confidence=Confidence(value=0.9, decay_profile=DecayProfile.TIME_LINEAR),
        target_face=TargetFace.ACTIVE_CONCERNS,
        source_function=SourceFunction.REFLECTION,
        evidence=[],
    )

    with patch("ze_worldstate.extraction.loop_to_contribution", return_value=mistagged):
        with pytest.raises(UnlicensedClaimKindError):
            await propose_loop_candidates(
                "remind me I need to follow up with the accountant",
                "user_declared",
                [],
                llm,
                embedder,
                loop_store,
                entity_resolver,
            )

    loop_store.create.assert_not_called()
