from __future__ import annotations

from ze_logging import get_logger
from ze_sdk.proactive import proactive_job

from ze_worldstate import drift
from ze_worldstate.errors import InvalidLoopTransitionError
from ze_worldstate.store import LoopStore
from ze_worldstate.types import LoopState

log = get_logger(__name__)


@proactive_job
class DriftSweepJob:
    job_id = "worldstate_drift_sweep"

    def __init__(self, loop_store: LoopStore) -> None:
        self._loop_store = loop_store

    async def run(self) -> None:
        for loop in await self._loop_store.list_drift_candidates():
            if not drift.is_drift_eligible(loop):
                continue
            try:
                await self._loop_store.transition(loop.id, LoopState.DRIFTING.value)
            except InvalidLoopTransitionError:
                log.info("open_loop_drift_skipped", loop_id=str(loop.id))
                continue
            await self._loop_store.set_drift_rationale(
                loop.id, drift.compose_absence_rationale(loop)
            )
            log.info("open_loop_drifted_from_sweep", loop_id=str(loop.id))
