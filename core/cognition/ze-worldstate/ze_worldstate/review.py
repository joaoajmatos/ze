from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from ze_logging import get_logger

from ze_worldstate import drift
from ze_worldstate.fingerprint import compute_evidence_fingerprint
from ze_worldstate.store import LoopStore
from ze_worldstate.types import DECLARED_CONFIDENCE, LoopState, OpenLoop

log = get_logger(__name__)


async def confirm_loop(loop_store: LoopStore, loop_id: UUID) -> OpenLoop:
    """Only valid from `suspected` (FR-007, FR-015).

    The user's confirmation is stamped like a declaration (0.9, a fresh drift
    window) so the page, REST and chat confirm all mean the same thing.
    Provenance is kept: the loop was still inferred.
    """
    loop = await loop_store.transition(loop_id, LoopState.ACTIVE.value)
    deadline = datetime.now(timezone.utc) + timedelta(
        days=drift.DEFAULT_DRIFT_WINDOW_DAYS
    )
    await loop_store.stamp_declared(
        loop_id, confidence=DECLARED_CONFIDENCE, deadline=deadline
    )
    loop.confidence = DECLARED_CONFIDENCE
    loop.drift_deadline = deadline
    loop.drift_rationale = None
    return loop


async def close_loop(loop_store: LoopStore, loop_id: UUID) -> OpenLoop:
    """Valid from `active`/`drifting` (FR-015)."""
    return await loop_store.transition(loop_id, LoopState.CLOSED.value)


async def drop_loop(loop_store: LoopStore, loop_id: UUID) -> OpenLoop:
    """Valid from any non-terminal state (FR-007, FR-015).

    Records the evidence fingerprint so the same evidence does not resurface
    the loop later (FR-011).
    """
    evidence_refs = await loop_store.list_evidence(loop_id)
    fingerprint = compute_evidence_fingerprint(evidence_refs)
    loop = await loop_store.transition(loop_id, LoopState.DROPPED.value)
    await loop_store.set_dismissed_evidence_fingerprint(loop_id, fingerprint)
    loop.dismissed_evidence_fingerprint = fingerprint
    log.info("open_loop_dropped", loop_id=str(loop_id), fingerprint=fingerprint)
    return loop
