from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol
from uuid import UUID

from ze_logging import get_logger
from ze_proactive.candidates import BarThresholds, PushCandidate
from ze_proactive.types import PushOutcome, is_sent

from ze_priority.push_bar import PushBar
from ze_priority.types import PriorityCandidateRef
from ze_priority.view import PriorityView

log = get_logger(__name__)


class PushCandidateSource(Protocol):
    """Structural: a source describes its candidates and sends one; it never
    applies the bar and never imports ze-priority."""

    source_kind: str
    thresholds: BarThresholds
    dry_run: bool

    async def candidates(self) -> list[PushCandidate]: ...

    async def send(self, candidate: PushCandidate) -> PushOutcome | None: ...


class AttentionArbitrationJob:
    """Sees every source's push candidates at once, applies the one push bar,
    and pushes only the highest-ranked survivor. The governor
    (`ProactiveNotifier`) owns the shared budget claim and the cooldowns; this
    job orders candidates and stops at the first one that is sent or held."""

    job_id = "attention_arbitration_sweep"

    def __init__(
        self,
        *,
        priority_view: PriorityView,
        sources: Sequence[PushCandidateSource],
        bar: PushBar,
        notifier: Any,
    ) -> None:
        self._priority_view = priority_view
        self._sources = sources
        self._bar = bar
        self._notifier = notifier

    async def run(self) -> None:
        if await self._notifier.remaining_budget() == 0:
            return

        passing: dict[tuple[str, UUID], tuple[PushCandidateSource, PushCandidate]] = {}
        for source in self._sources:
            for candidate in await self._screened(source):
                passing[(candidate.source_kind, candidate.source_id)] = (
                    source,
                    candidate,
                )

        if not passing:
            return

        ranking = await self._priority_view.rank_subset(
            [
                PriorityCandidateRef(candidate.source_kind, candidate.entity)
                for _, candidate in passing.values()
            ]
        )

        for item in ranking.items:
            found = passing.get((item.source_kind, item.source_id))
            if found is None:
                continue
            source, candidate = found

            outcome = await source.send(candidate)
            if is_sent(outcome):
                log.info(
                    "attention_arbitration_pushed",
                    source_kind=candidate.source_kind,
                    source_id=str(candidate.source_id),
                    outcome=outcome,
                )
                return
            if outcome == "suppressed_budget":
                log.info(
                    "attention_arbitration_budget_arbitrated",
                    source_kind=candidate.source_kind,
                    source_id=str(candidate.source_id),
                )
                return
            log.info(
                "attention_arbitration_candidate_skipped",
                source_kind=candidate.source_kind,
                source_id=str(candidate.source_id),
                outcome=outcome,
            )

    async def _screened(self, source: PushCandidateSource) -> list[PushCandidate]:
        try:
            candidates = await source.candidates()
        except Exception as exc:
            log.warning(
                "attention_arbitration_source_failed",
                source_kind=source.source_kind,
                error=str(exc),
            )
            return []

        # A cooling candidate is dropped before the bar so it costs no
        # embedding or NLI work.
        awake: list[PushCandidate] = []
        for candidate in candidates:
            if await self._notifier.on_cooldown(candidate.once_per):
                log.info(
                    "push_candidate_cooling",
                    source_kind=candidate.source_kind,
                    source_id=str(candidate.source_id),
                )
            else:
                awake.append(candidate)

        passed: list[PushCandidate] = []
        for verdict in await self._bar.screen(awake, source.thresholds):
            candidate = verdict.candidate
            if not verdict.passed:
                log.info(
                    "push_bar_rejected",
                    source_kind=candidate.source_kind,
                    source_id=str(candidate.source_id),
                    reason=verdict.reason,
                )
            elif source.dry_run:
                log.info(
                    "push_candidate_dry_run",
                    source_kind=candidate.source_kind,
                    source_id=str(candidate.source_id),
                    body=candidate.body,
                )
            else:
                passed.append(candidate)
        return passed
