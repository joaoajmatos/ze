from __future__ import annotations

from typing import Any

from ze_logging import get_logger

from ze_priority.types import PriorityCandidateRef
from ze_priority.view import PriorityView

log = get_logger(__name__)


class AttentionArbitrationJob:
    """Replaces `ze_worldstate.jobs.push_sweep.PushSweepJob` and
    `ze-correlation`'s autonomous scheduled push trigger with one job that sees
    every mechanism's push-eligible candidates at once and pushes only the
    highest-ranked one (FR-007, FR-008). The governor (`ProactiveNotifier`) owns
    the shared budget claim; this job only orders candidates and stops at the
    first one that is sent or held."""

    job_id = "attention_arbitration_sweep"

    def __init__(
        self,
        priority_view: PriorityView,
        loop_surfacer: Any,
        correlation_push_source: Any,
        notifier: Any,
    ) -> None:
        self._priority_view = priority_view
        self._loop_surfacer = loop_surfacer
        self._correlation_push_source = correlation_push_source
        self._notifier = notifier

    async def run(self) -> None:
        if await self._notifier.remaining_budget() == 0:
            return

        loop_candidates = await self._loop_surfacer.eligible_candidates()
        hypothesis_candidates = (
            await self._correlation_push_source.eligible_candidates()
        )

        if not loop_candidates and not hypothesis_candidates:
            return

        refs = [
            PriorityCandidateRef(source_kind="loop", entity=c) for c in loop_candidates
        ] + [
            PriorityCandidateRef(source_kind="hypothesis", entity=c)
            for c in hypothesis_candidates
        ]
        ranking = await self._priority_view.rank_subset(refs)

        loops_by_id = {c.id: c for c in loop_candidates}
        hypotheses_by_id = {c.id: c for c in hypothesis_candidates}

        for item in ranking.items:
            entity = (
                loops_by_id.get(item.source_id)
                if item.source_kind == "loop"
                else hypotheses_by_id.get(item.source_id)
            )
            if entity is None:
                continue

            outcome = await self._send(item.source_kind, entity)
            if outcome in ("delivered", "held"):
                log.info(
                    "attention_arbitration_pushed",
                    source_kind=item.source_kind,
                    source_id=str(item.source_id),
                    outcome=outcome,
                )
                return
            if outcome == "suppressed_budget":
                log.info(
                    "attention_arbitration_budget_arbitrated",
                    source_kind=item.source_kind,
                    source_id=str(item.source_id),
                )
                return
            log.info(
                "attention_arbitration_candidate_skipped",
                source_kind=item.source_kind,
                source_id=str(item.source_id),
                outcome=outcome,
            )

    async def _send(self, source_kind: str, entity: Any) -> str | None:
        if source_kind == "loop":
            return await self._loop_surfacer.send(entity)
        return await self._correlation_push_source.send(entity)
