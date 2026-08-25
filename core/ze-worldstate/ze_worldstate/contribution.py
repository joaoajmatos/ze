"""Conversion from ze-worldstate's `OpenLoop` into the shared `Contribution` seam type."""

from __future__ import annotations

from ze_agents.claims import Confidence, DecayProfile, Provenance
from ze_plugin.contribution import Contribution, EvidenceRef, SourceFunction, TargetFace

from ze_worldstate.types import LoopProvenance, OpenLoop

_INFLOW_TO_EPISTEMIC: dict[str, Provenance] = {
    LoopProvenance.USER_DECLARED: Provenance.PROMPT_SUPPLIED,
    LoopProvenance.CONVERSATION: Provenance.SYNTHESIZED,
    LoopProvenance.INGESTION: Provenance.SYNTHESIZED,
}


def loop_to_contribution(
    loop: OpenLoop, evidence: list[EvidenceRef] | None = None
) -> Contribution:
    return Contribution(
        claim_kind=loop.claim_kind,
        provenance=_INFLOW_TO_EPISTEMIC.get(loop.provenance, Provenance.SYNTHESIZED),
        confidence=Confidence(
            value=loop.confidence,
            decay_profile=DecayProfile.TIME_LINEAR,
        ),
        target_face=TargetFace.ACTIVE_CONCERNS,
        source_function=SourceFunction.EXECUTIVE,
        evidence=evidence or [],
    )
