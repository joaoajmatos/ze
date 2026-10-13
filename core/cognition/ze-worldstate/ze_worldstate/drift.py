from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from ze_worldstate.types import LoopState, OpenLoop

# Clarification-pinned default — used whenever the extraction gate doesn't
# supply an implied window (research.md §1).
DEFAULT_DRIFT_WINDOW_DAYS = 7


def compute_drift_deadline(
    confirmed_at: datetime, implied_window_days: int | None = None
) -> datetime:
    """One-time deadline computation at confirm-time (research.md §1)."""
    window = implied_window_days or DEFAULT_DRIFT_WINDOW_DAYS
    return confirmed_at + timedelta(days=window)


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
