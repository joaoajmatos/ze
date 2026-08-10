from __future__ import annotations

from ze_logging import get_logger
from ze_proactive.staleness import is_stale
from ze_sdk.proactive import proactive_job

from ze_worldstate import drift
from ze_worldstate.store import LoopStore
from ze_worldstate.types import LoopState

log = get_logger(__name__)


@proactive_job
class DriftSweepJob:
    job_id = "worldstate_drift_sweep"

    def __init__(self, loop_store: LoopStore) -> None:
        self._loop_store = loop_store

    async def run(self) -> None:
        candidates = await self._loop_store.list_drift_candidates()
        for loop in candidates:
            if not is_stale(loop.drift_deadline, window_days=0):
                continue
            if not drift.is_drift_eligible(loop):
                continue
            rationale = drift.compose_absence_rationale(loop)
            await self._loop_store.transition(loop.id, LoopState.DRIFTING.value)
            await self._loop_store.set_drift_rationale(loop.id, rationale)
            log.info("open_loop_drifted_from_sweep", loop_id=str(loop.id))
