"""Deterministic evidence weighting and corroboration gate for co-occurrence
inference (Phase 130).

No LLM call anywhere in this module (FR-004) — `SOURCE_WEIGHTS` is reused
verbatim from `ze_personal.contacts.types`, the same table contact extraction
already trusts. `ze_correlation` stays domain-agnostic; this module is where
"person"/"project" co-occurrence scoring actually lives (research.md Decision
2).
"""

from __future__ import annotations

from ze_proactive.staleness import is_stale

from ze_personal.contacts.types import SOURCE_WEIGHTS
from ze_personal.social.types import CoOccurrenceEvidenceEvent

RECENCY_WINDOW_DAYS = 30

# research.md Decision 3: 2 independent events (distinct `event_id`s) spanning
# 2 distinct calendar days inside the recency window.
MIN_CORROBORATING_EVENTS = 2
MIN_CORROBORATING_DAYS = 2


def _event_weight(event: CoOccurrenceEvidenceEvent) -> float:
    """A same-thread reply/attendee is the event's own source-type tier; a
    CC-only / no-reply mention is always research-tier (FR-004)."""
    if not event.is_reply_or_attendee:
        return SOURCE_WEIGHTS["research"]
    return SOURCE_WEIGHTS[event.source_type]


def filter_fresh_evidence(
    events: list[CoOccurrenceEvidenceEvent],
    *,
    window_days: int = RECENCY_WINDOW_DAYS,
) -> list[CoOccurrenceEvidenceEvent]:
    """Evidence outside the recency window MUST NOT count (FR-003)."""
    return [e for e in events if not is_stale(e.occurred_at, window_days)]


def score_evidence(events: list[CoOccurrenceEvidenceEvent]) -> float:
    """Weighted-average confidence over fresh evidence, capped at 1.0.

    Already-stale events must be filtered via `filter_fresh_evidence()` before
    calling this — it does not re-check the window itself, to keep the two
    concerns (freshness vs. weighting) independently testable.
    """
    if not events:
        return 0.0
    weights = [_event_weight(e) for e in events]
    return min(1.0, sum(weights) / len(weights))


def is_corroborated(events: list[CoOccurrenceEvidenceEvent]) -> bool:
    """research.md Decision 3 — distinct events across distinct days, not a
    raw confidence threshold, so a single high-weight event can never promote
    on its own (User Story 3's over-confidence risk)."""
    distinct_event_ids = {e.event_id for e in events}
    if len(distinct_event_ids) < MIN_CORROBORATING_EVENTS:
        return False
    distinct_days = {e.occurred_at.date() for e in events}
    return len(distinct_days) >= MIN_CORROBORATING_DAYS
