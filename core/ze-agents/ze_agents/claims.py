"""Shared claim vocabulary — kind, provenance, and decay math every producer speaks.

`Provenance` is deliberately closed to exactly four epistemic-origin values and MUST
NEVER gain a member naming a specific plugin, channel, or inflow mechanism (FR-002;
specs/arch/plugin-domain-vocabulary.md). A caller's own inflow channel is a
plugin-owned string (see `OpenLoop.provenance`, `Signal.source`), not a member here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ze_agents.errors import MissingDecayParameterError

CONFIDENCE_FLOOR = 0.05
_TIME_LINEAR_RATE = 0.03
_TIME_LINEAR_PERIOD_DAYS = 30.0


class ClaimKind(StrEnum):
    IDENTITY = "identity"
    FACT = "fact"
    INFERENCE = "inference"
    SUSPICION = "suspicion"
    PRIORITY = "priority"


class Provenance(StrEnum):
    GRAPH_RECALL = "graph_recall"
    LIVE_SEARCH = "live_search"
    PROMPT_SUPPLIED = "prompt_supplied"
    SYNTHESIZED = "synthesized"


class DecayProfile(StrEnum):
    EVIDENCE_WEIGHTED = "evidence_weighted"
    TIME_LINEAR = "time_linear"


@dataclass
class Confidence:
    value: float
    decay_profile: DecayProfile


def decay(
    value: float,
    decay_profile: DecayProfile,
    *,
    remaining_evidence: int | None = None,
    total_evidence: int | None = None,
    elapsed_days: float | None = None,
) -> float:
    """Dispatch on `decay_profile` — callers own persistence, this is pure math."""
    if decay_profile == DecayProfile.EVIDENCE_WEIGHTED:
        if remaining_evidence is None or total_evidence is None:
            raise MissingDecayParameterError(
                "EVIDENCE_WEIGHTED decay requires remaining_evidence and total_evidence"
            )
        if total_evidence <= 1:
            return CONFIDENCE_FLOOR
        return max(CONFIDENCE_FLOOR, value * remaining_evidence / total_evidence)

    if decay_profile == DecayProfile.TIME_LINEAR:
        if elapsed_days is None:
            raise MissingDecayParameterError(
                "TIME_LINEAR decay requires elapsed_days"
            )
        periods = int(elapsed_days // _TIME_LINEAR_PERIOD_DAYS)
        return max(0.0, value - _TIME_LINEAR_RATE * periods)

    raise MissingDecayParameterError(f"unknown decay_profile: {decay_profile!r}")
