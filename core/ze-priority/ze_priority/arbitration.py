from __future__ import annotations

from typing import Any

from ze_logging import get_logger
from ze_proactive.attention_budget import release_shared, try_claim_shared

from ze_priority.types import PriorityCandidateRef
from ze_priority.view import PriorityView

log = get_logger(__name__)


class AttentionArbitrationJob:
    """Replaces `ze_worldstate.jobs.push_sweep.PushSweepJob` and
    `ze-correlation`'s autonomous scheduled push trigger with one job that sees
    every mechanism's push-eligible candidates at once and pushes only the
    highest-ranked one (FR-007, FR-008)."""

    job_id = "attention_arbitration_sweep"

    def __init__(
        self,
        priority_view: PriorityView,
        loop_surfacer: Any,
        correlation_push_source: Any,
        push_log: Any,
        max_pushes_per_day: int,
    ) -> None:
        self._priority_view = priority_view
        self._loop_surfacer = loop_surfacer
        self._correlation_push_source = correlation_push_source
        self._push_log = push_log
        self._max_pushes_per_day = max_pushes_per_day

    async def run(self) -> None:
        loop_candidates = await self._loop_surfacer.eligible_candidates()
        hypothesis_candidates = await self._correlation_push_source.eligible_candidates()

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

            claimed = await try_claim_shared(
                self._push_log,
                item.source_kind,
                item.source_id,
                self._max_pushes_per_day,
            )
            if not claimed:
                log.info(
                    "attention_arbitration_budget_arbitrated",
                    source_kind=item.source_kind,
                    source_id=str(item.source_id),
                )
                continue

            sent = await self._send(item.source_kind, entity)
            if not sent:
                await release_shared(self._push_log, item.source_kind, item.source_id)
                log.warning(
                    "attention_arbitration_send_failed",
                    source_kind=item.source_kind,
                    source_id=str(item.source_id),
                )
                continue

            log.info(
                "attention_arbitration_pushed",
                source_kind=item.source_kind,
                source_id=str(item.source_id),
            )
            return

    async def _send(self, source_kind: str, entity: Any) -> bool:
        if source_kind == "loop":
            return await self._loop_surfacer.send(entity)
        return await self._correlation_push_source.send(entity)
