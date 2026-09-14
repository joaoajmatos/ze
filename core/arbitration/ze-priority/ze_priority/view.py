from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from ze_logging import get_logger

from ze_automation.goals.store import GoalStore
from ze_correlation.jobs.hypothesis_decay import DEFAULT_DECAY_WINDOW_DAYS
from ze_correlation.store import PostgresHypothesisStore
from ze_worldstate.store import LoopStore
from ze_worldstate.types import LoopState

from ze_priority.errors import ZePriorityError
from ze_priority.scoring import (
    score_goal,
    score_hypothesis,
    score_loop,
    score_relationship_staleness,
    sort_and_rank,
)
from ze_priority.types import (
    PriorityCandidateRef,
    PriorityItem,
    PriorityRanking,
    RelationshipStalenessSource,
    SourceKind,
)

log = get_logger(__name__)

UTC = timezone.utc

# No progress-cooldown or idleness floor applied here — PriorityView is a ranking
# query, not the alerting job (StuckGoalJob); any idle goal is a candidate, and
# scoring.score_goal differentiates urgency by idle_days magnitude.
_GOAL_MIN_IDLE_DAYS = 0
_GOAL_ALERT_COOLDOWN_DAYS = 0

_OPEN_LOOP_STATES = [LoopState.ACTIVE.value, LoopState.DRIFTING.value]

# ze-priority owns its own relationship-staleness thresholds, analogous to how
# loop/goal staleness thresholds are owned by their respective core packages —
# not read from plugins/ze-personal's briefing config (research.md §6).
_RELATIONSHIP_STALE_DAYS_DEFAULT = 7
_RELATIONSHIP_LIMIT_DEFAULT = 3


class PriorityView:
    """Read-only projection ranking open loops, stuck/near-gate goals,
    non-stale hypotheses, and stale relationships on one comparable
    `Confidence` scale (FR-001..FR-004)."""

    def __init__(
        self,
        loop_store: LoopStore,
        goal_store: GoalStore,
        hypothesis_store: PostgresHypothesisStore,
        relationship_source: RelationshipStalenessSource | None = None,
    ) -> None:
        self._loop_store = loop_store
        self._goal_store = goal_store
        self._hypothesis_store = hypothesis_store
        self._relationship_source = relationship_source

    def set_relationship_source(self, source: RelationshipStalenessSource) -> None:
        """Backfill the relationship source after construction.

        Composition-root escape hatch for the one genuine wiring-order cycle:
        `PriorityView` is injected into `PersonalPlugin` (for `MorningBriefing`)
        before `PersonalPlugin` constructs the `PersonStore` this source needs.
        """
        self._relationship_source = source

    async def rank(self) -> PriorityRanking:
        """Queries every configured source, degrading per-source on error (FR-009).
        Raises `ZePriorityError` only if all configured sources fail."""
        items: list[PriorityItem] = []
        succeeded: set[SourceKind] = set()
        failed: set[SourceKind] = set()
        total_sources = 3

        try:
            loops = await self._loop_store.list(_OPEN_LOOP_STATES)
            items.extend(score_loop(loop) for loop in loops)
            succeeded.add("loop")
        except Exception as exc:
            log.warning("priority_view_loop_source_failed", error=str(exc))
            failed.add("loop")

        try:
            stuck = await self._goal_store.list_stuck(
                idle_days=_GOAL_MIN_IDLE_DAYS,
                alert_cooldown_days=_GOAL_ALERT_COOLDOWN_DAYS,
            )
            items.extend(score_goal(sg) for sg in stuck)
            succeeded.add("goal")
        except Exception as exc:
            log.warning("priority_view_goal_source_failed", error=str(exc))
            failed.add("goal")

        try:
            hypotheses = await self._hypothesis_store.list_recent(
                DEFAULT_DECAY_WINDOW_DAYS
            )
            items.extend(score_hypothesis(h) for h in hypotheses)
            succeeded.add("hypothesis")
        except Exception as exc:
            log.warning("priority_view_hypothesis_source_failed", error=str(exc))
            failed.add("hypothesis")

        if self._relationship_source is not None:
            total_sources += 1
            try:
                nudges = await self._relationship_source.list_stale_for_follow_up(
                    _RELATIONSHIP_STALE_DAYS_DEFAULT, _RELATIONSHIP_LIMIT_DEFAULT
                )
                items.extend(score_relationship_staleness(n) for n in nudges)
                succeeded.add("relationship")
            except Exception as exc:
                log.warning(
                    "priority_view_relationship_source_failed", error=str(exc)
                )
                failed.add("relationship")

        if len(failed) == total_sources:
            raise ZePriorityError("all PriorityView sources failed")

        return PriorityRanking(
            items=sort_and_rank(items),
            sources_succeeded=succeeded,
            sources_failed=failed,
            generated_at=datetime.now(UTC),
        )

    async def rank_subset(
        self, candidates: Sequence[PriorityCandidateRef]
    ) -> PriorityRanking:
        """Same ranking logic as `rank()`, scoped to already-fetched candidates —
        never re-queries the stores (used by `AttentionArbitrationJob`)."""
        items: list[PriorityItem] = []
        succeeded: set[SourceKind] = set()

        for candidate in candidates:
            if candidate.source_kind == "loop":
                items.append(score_loop(candidate.entity))
            elif candidate.source_kind == "goal":
                items.append(score_goal(candidate.entity))
            else:
                items.append(score_hypothesis(candidate.entity))
            succeeded.add(candidate.source_kind)

        return PriorityRanking(
            items=sort_and_rank(items),
            sources_succeeded=succeeded,
            sources_failed=set(),
            generated_at=datetime.now(UTC),
        )
