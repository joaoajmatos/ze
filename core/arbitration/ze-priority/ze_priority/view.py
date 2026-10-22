from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Sequence

from ze_logging import get_logger

from ze_automation.goals.store import GoalStore
from ze_correlation.jobs.hypothesis_decay import DEFAULT_DECAY_WINDOW_DAYS
from ze_correlation.store import PostgresHypothesisStore
from ze_worldstate.store import LoopStore
from ze_worldstate.types import LoopState

from ze_priority.errors import ZePriorityError
from ze_priority.merge import merge
from ze_priority.scoring import (
    score_goal,
    score_hypothesis,
    score_loop,
    score_relationship_staleness,
    sort_and_rank,
)
from ze_priority.store import PriorityOverrideStore
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


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PriorityView:
    """Read-only projection ranking open loops, stuck/near-gate goals,
    non-stale hypotheses, and stale relationships on one comparable
    `Confidence` scale (FR-001..FR-004), in the user's order: active
    reprioritization overrides are merged here, so every consumer sees one
    order. `rank` is the displayed rank; `computed_rank` is Ze's own."""

    def __init__(
        self,
        loop_store: LoopStore,
        goal_store: GoalStore,
        hypothesis_store: PostgresHypothesisStore,
        relationship_source: RelationshipStalenessSource | None = None,
        *,
        override_store: PriorityOverrideStore | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._loop_store = loop_store
        self._goal_store = goal_store
        self._hypothesis_store = hypothesis_store
        self._relationship_source = relationship_source
        self._override_store = override_store
        self._clock = clock

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
                log.warning("priority_view_relationship_source_failed", error=str(exc))
                failed.add("relationship")

        if len(failed) == total_sources:
            raise ZePriorityError("all PriorityView sources failed")

        ranking = PriorityRanking(
            items=sort_and_rank(items),
            sources_succeeded=succeeded,
            sources_failed=failed,
            generated_at=self._clock(),
        )
        return await self._apply_overrides(ranking)

    async def _apply_overrides(self, ranking: PriorityRanking) -> PriorityRanking:
        if self._override_store is None or not ranking.items:
            return ranking
        try:
            overrides = await self._override_store.get_active()
        except Exception as exc:
            log.warning("priority_overrides_unavailable", error=str(exc))
            return ranking

        items_by_id = {item.source_id: item for item in ranking.items}
        ordered: list[PriorityItem] = []
        for row in merge(ranking, overrides, self._clock()):
            item = items_by_id[row.source_id]
            item.rank = row.displayed_rank
            item.override = row.override
            ordered.append(item)
        ranking.items = ordered
        return ranking

    async def rank_subset(
        self, candidates: Sequence[PriorityCandidateRef]
    ) -> PriorityRanking:
        """The already-fetched `candidates`, in their place in the full `rank()`
        (the user's order), minus any item the user pushed down while its
        override is active (used by `AttentionArbitrationJob`). A candidate the
        full ranking does not hold keeps its own score and follows the rest."""
        try:
            full = await self.rank()
        except ZePriorityError:
            full = None
        known = {item.source_id: item for item in full.items} if full else {}

        placed: list[PriorityItem] = []
        unplaced: list[PriorityItem] = []
        succeeded: set[SourceKind] = set()
        for candidate in candidates:
            scored = _score_candidate(candidate)
            item = known.get(scored.source_id)
            if item is None:
                unplaced.append(scored)
            elif not _is_pushed_down(item):
                placed.append(item)
            succeeded.add(candidate.source_kind)

        placed.sort(key=lambda item: item.rank)
        return PriorityRanking(
            items=placed + sort_and_rank(unplaced),
            sources_succeeded=succeeded,
            sources_failed=set(),
            generated_at=self._clock(),
        )


def _score_candidate(candidate: PriorityCandidateRef) -> PriorityItem:
    if candidate.source_kind == "loop":
        return score_loop(candidate.entity)
    if candidate.source_kind == "goal":
        return score_goal(candidate.entity)
    return score_hypothesis(candidate.entity)


def _is_pushed_down(item: PriorityItem) -> bool:
    """An active override (merge keeps only those with weight > 0) that put the
    item below where Ze's own score would."""
    return item.override is not None and item.rank > item.computed_rank
