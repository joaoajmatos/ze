"""Conversion from ze-memory's `Signal` into the shared `Contribution` seam type."""

from __future__ import annotations

from ze_agents.claims import ClaimKind, Confidence, DecayProfile
from ze_plugin.contribution import Contribution, SourceFunction, TargetFace

from ze_memory.types import Signal


def signal_to_contribution(signal: Signal) -> Contribution:
    return Contribution(
        claim_kind=ClaimKind.FACT,
        provenance=signal.provenance,
        confidence=Confidence(
            value=signal.confidence,
            decay_profile=DecayProfile.TIME_LINEAR,
        ),
        target_face=TargetFace.WORLD,
        source_function=SourceFunction.PERCEPTION,
        evidence=[],
    )
