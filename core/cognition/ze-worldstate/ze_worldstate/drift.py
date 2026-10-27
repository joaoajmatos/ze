from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from ze_worldstate.types import LoopState, OpenLoop


def is_drift_eligible(loop: OpenLoop, now: datetime | None = None) -> bool:
    """Mirrors `list_drift_candidates`'s SQL predicate for in-process checks/tests."""
    now = now or datetime.now(timezone.utc)
    if loop.state != LoopState.ACTIVE or loop.drift_deadline is None:
        return False
    deadline = loop.drift_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return deadline <= now


def compose_absence_rationale(loop: OpenLoop) -> str:
    """Hedged rationale for the sweep path (FR-004)."""
    deadline_s = (
        loop.drift_deadline.date().isoformat() if loop.drift_deadline else "unknown"
    )
    return (
        "No corroborating evidence (email, calendar, or conversational update) "
        f"before the implied window elapsed on {deadline_s}."
    )


def compose_contradiction_rationale(evidence_type: str, evidence_id: UUID) -> str:
    """Hedged, evidence-cited rationale for the immediate contradiction path (FR-002)."""
    return (
        f"Contradicted by new {evidence_type} evidence ({evidence_id}); "
        "confidence dropped below the active threshold."
    )
