"""Corroboration — the independence rule and the confidence arithmetic.

Pure policy for phase 172. A text corroborates a suspected loop only when it comes from a source
the loop has not already counted (specs/phases/172-corroboration-promotion/contracts/).
"""

from __future__ import annotations

from collections.abc import Sequence

from ze_logging import get_logger
from ze_plugin.contribution import EvidenceRef

from ze_worldstate.drift import DEFAULT_DRIFT_WINDOW_DAYS
from ze_worldstate.types import LoopSource, SourceKey

log = get_logger(__name__)

CORROBORATION_WEIGHT = 0.5
CORROBORATED_CAP = 0.6
PROMOTED_CONFIDENCE = 0.7
PROMOTED_WINDOW_DAYS = DEFAULT_DRIFT_WINDOW_DAYS


def is_independent(
    key: SourceKey | None,
    new_evidence: Sequence[EvidenceRef],
    loop_sources: Sequence[LoopSource],
    loop_evidence: Sequence[EvidenceRef],
    dropped_sources: Sequence[LoopSource],
) -> tuple[bool, str]:
    """Pure. Returns (independent, reason); the reason is only for the log."""
    if key is None or not key.ref:
        return False, "no_key"
    if key in {s.key for s in loop_sources}:
        return False, "same_source"
    known = {(e.kind, e.id) for e in loop_evidence}
    if any((e.kind, e.id) in known for e in new_evidence):
        return False, "same_evidence"
    if key in {s.key for s in dropped_sources}:
        return False, "dropped_source"
    return True, "independent"


def corroborated_confidence(confidence: float, score: float) -> float:
    """Noisy-OR with the score as a weight, capped below the promoted level."""
    raised = 1 - (1 - confidence) * (1 - CORROBORATION_WEIGHT * score)
    return min(CORROBORATED_CAP, max(confidence, raised))
