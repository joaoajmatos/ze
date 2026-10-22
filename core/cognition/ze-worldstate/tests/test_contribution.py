from __future__ import annotations

from uuid import uuid4

from ze_agents.claims import ClaimKind, DecayProfile, Provenance
from ze_plugin.contribution import EvidenceRef, SourceFunction, TargetFace

from ze_worldstate.contribution import loop_to_contribution
from ze_worldstate.types import (
    LoopClaimKind,
    LoopProvenance,
    LoopState,
    OpenLoop,
)


def _make_loop(**kwargs) -> OpenLoop:
    defaults = dict(
        title="Renew passport",
        provenance=LoopProvenance.CONVERSATION,
        confidence=0.3,
        state=LoopState.SUSPECTED,
    )
    defaults.update(kwargs)
    return OpenLoop(**defaults)


# ── loop_to_contribution round-trip ────────────────────────────────────────────


def test_loop_to_contribution_preserves_claim_kind_and_confidence():
    loop = _make_loop(state=LoopState.ACTIVE, confidence=0.9)

    contribution = loop_to_contribution(loop)

    assert contribution.claim_kind == LoopClaimKind.PRIORITY
    assert contribution.confidence.value == 0.9
    assert contribution.confidence.decay_profile == DecayProfile.TIME_LINEAR
    assert contribution.source_function == SourceFunction.EXECUTIVE
    assert contribution.target_face == TargetFace.ACTIVE_CONCERNS


def test_loop_to_contribution_maps_inflow_provenance_to_epistemic():
    assert (
        loop_to_contribution(
            _make_loop(provenance=LoopProvenance.USER_DECLARED)
        ).provenance
        == Provenance.PROMPT_SUPPLIED
    )
    assert (
        loop_to_contribution(
            _make_loop(provenance=LoopProvenance.CONVERSATION)
        ).provenance
        == Provenance.SYNTHESIZED
    )
    assert (
        loop_to_contribution(_make_loop(provenance=LoopProvenance.INGESTION)).provenance
        == Provenance.SYNTHESIZED
    )


def test_loop_to_contribution_carries_evidence_through():
    contribution_evidence = [EvidenceRef(kind="fact", id=uuid4())]

    contribution = loop_to_contribution(_make_loop(), evidence=contribution_evidence)

    assert contribution.evidence == contribution_evidence


# ── claim kind comes from the state at the write path (FR-012) ─────────────────


def test_contribution_for_a_new_suspected_loop_declares_suspicion():
    contribution = loop_to_contribution(_make_loop(state=LoopState.SUSPECTED))

    assert contribution.claim_kind is ClaimKind.SUSPICION


def test_contribution_for_a_declared_active_loop_declares_priority():
    contribution = loop_to_contribution(
        _make_loop(state=LoopState.ACTIVE, provenance=LoopProvenance.USER_DECLARED)
    )

    assert contribution.claim_kind is ClaimKind.PRIORITY
