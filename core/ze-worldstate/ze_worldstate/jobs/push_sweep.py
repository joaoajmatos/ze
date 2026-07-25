from __future__ import annotations

from typing import Any

from ze_logging import get_logger
from ze_sdk.proactive import proactive_job

from ze_worldstate.store import LoopStore
from ze_worldstate.surfacing import LoopSurfacer, format_hedged_mention
from ze_worldstate.types import LoopState

log = get_logger(__name__)

_DEFAULT_THRESHOLDS = {
    "tau_confidence": 0.5,
    "tau_relevance": 0.5,
    "novelty_similarity_max": 0.85,
    "grounding_threshold": 0.3,
}


@proactive_job
class PushSweepJob:
    job_id = "worldstate_push_sweep"

    def __init__(
        self,
        loop_store: LoopStore,
        surfacer: LoopSurfacer,
        notifier: Any,
        *,
        max_pushes_per_day: int = 3,
        inline_cooldown_hours: float = 12.0,
        thresholds: dict | None = None,
        nli_client: Any = None,
    ) -> None:
        self._loop_store = loop_store
        self._surfacer = surfacer
        self._notifier = notifier
        self._max_pushes_per_day = max_pushes_per_day
        self._inline_cooldown_hours = inline_cooldown_hours
        self._thresholds = {**_DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._nli_client = nli_client

    async def run(self) -> None:
        loops = await self._loop_store.list([LoopState.DRIFTING.value])
        for loop in loops:
            if not loop.drift_rationale:
                continue

            passes = await self._surfacer.passes_push_bar(
                loop,
                loop.drift_rationale,
                tau_confidence=self._thresholds["tau_confidence"],
                tau_relevance=self._thresholds["tau_relevance"],
                novelty_similarity_max=self._thresholds["novelty_similarity_max"],
                grounding_threshold=self._thresholds["grounding_threshold"],
                max_pushes_per_day=self._max_pushes_per_day,
                inline_cooldown_hours=self._inline_cooldown_hours,
                nli_client=self._nli_client,
            )
            if not passes:
                continue

            # FR-011: re-check current lifecycle state immediately before sending —
            # the loop may have been closed/dropped between selection and send.
            current = await self._loop_store.get(loop.id)
            if current is None or current.state != LoopState.DRIFTING:
                continue

            body = format_hedged_mention(loop.title, loop.drift_rationale)
            await self._notifier.push(body, urgency="normal")
            await self._surfacer.log_push(loop.id, loop.drift_rationale)
            log.info("open_loop_pushed", loop_id=str(loop.id))
