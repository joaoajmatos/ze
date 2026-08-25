from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ze_agents.claims import ClaimKind, Confidence, DecayProfile, decay
from ze_automation.goals.types import StuckGoal
from ze_correlation.types import Hypothesis
from ze_worldstate.types import LoopState, OpenLoop

from ze_priority.types import (
    GoalSignal,
    HypothesisSignal,
    LoopSignal,
    PriorityItem,
)

UTC = timezone.utc

_DRIFTING_STATE_BONUS = 0.3
_DRIFTING_DAILY_BONUS = 0.05
_DRIFTING_DAILY_BONUS_CAP = 0.5


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _elapsed_days(reference: datetime | None, now: datetime) -> float:
    if reference is None:
        return 0.0
    return max(0.0, (now - _as_aware(reference)).total_seconds() / 86400.0)


def score_loop(loop: OpenLoop, *, now: datetime | None = None) -> PriorityItem:
    """Wraps `OpenLoop.confidence`/`state` — never recomputes drift detection (FR-003)."""
    now = now or datetime.now(UTC)
    value = loop.confidence
    if loop.state == LoopState.DRIFTING:
        elapsed_days = _elapsed_days(loop.updated_at or loop.created_at, now)
        value += _DRIFTING_STATE_BONUS + min(
            elapsed_days * _DRIFTING_DAILY_BONUS, _DRIFTING_DAILY_BONUS_CAP
        )
    value = max(0.0, min(1.0, value))
    activity_at = loop.updated_at or loop.created_at or now

    assert loop.id is not None
    return PriorityItem(
        source_kind="loop",
        claim_kind=loop.claim_kind,
        source_id=loop.id,
        title=loop.title,
        signal=LoopSignal(
            state=loop.state,
            confidence=loop.confidence,
            drift_deadline=loop.drift_deadline,
        ),
        priority=Confidence(value=value, decay_profile=DecayProfile.TIME_LINEAR),
        rank=0,
        activity_at=_as_aware(activity_at),
    )


def score_goal(stuck: StuckGoal, *, now: datetime | None = None) -> PriorityItem:
    """Urgency = complement of the shared `decay()` freshness curve applied to
    `idle_days` — reuses the existing normalization function rather than
    inventing a new one (FR-003), per research.md."""
    now = now or datetime.now(UTC)
    freshness = decay(1.0, DecayProfile.TIME_LINEAR, elapsed_days=float(stuck.idle_days))
    urgency = max(0.0, min(1.0, 1.0 - freshness))
    activity_at = now - timedelta(days=stuck.idle_days)

    assert stuck.goal.id is not None
    return PriorityItem(
        source_kind="goal",
        claim_kind=ClaimKind.PRIORITY,
        source_id=stuck.goal.id,
        title=stuck.goal.title,
        signal=GoalSignal(kind=stuck.kind, idle_days=stuck.idle_days),
        priority=Confidence(value=urgency, decay_profile=DecayProfile.TIME_LINEAR),
        rank=0,
        activity_at=activity_at,
    )


def score_hypothesis(hyp: Hypothesis, *, now: datetime | None = None) -> PriorityItem:
    """Combines `confidence` and `relevance` as-is — both already computed by
    `ze-correlation`, never recomputed here (FR-003)."""
    value = max(0.0, min(1.0, hyp.confidence * hyp.relevance))
    return PriorityItem(
        source_kind="hypothesis",
        claim_kind=hyp.claim_kind,
        source_id=hyp.id,
        title=hyp.summary,
        signal=HypothesisSignal(confidence=hyp.confidence, relevance=hyp.relevance),
        priority=Confidence(value=value, decay_profile=DecayProfile.EVIDENCE_WEIGHTED),
        rank=0,
        activity_at=_as_aware(hyp.created_at),
    )


def sort_and_rank(items: list[PriorityItem]) -> list[PriorityItem]:
    """Sort by `priority.value` descending; deterministic tie-break by
    `activity_at` descending, then `source_id` ascending (contracts/priority_view.md)."""
    ordered = sorted(
        items,
        key=lambda item: (
            -item.priority.value,
            -item.activity_at.timestamp(),
            item.source_id,
        ),
    )
    for index, item in enumerate(ordered, start=1):
        item.rank = index
    return ordered
