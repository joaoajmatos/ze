from __future__ import annotations

from ze_logging import get_logger
from ze_proactive.job import proactive_job

from ze_worldstate import drift
from ze_worldstate.errors import InvalidLoopTransitionError, LoopNotFoundError
from ze_worldstate.lifecycle import LoopLifecycle
from ze_worldstate.store import LoopStore

log = get_logger(__name__)


@proactive_job
class DriftSweepJob:
    job_id = "worldstate_drift_sweep"

    def __init__(self, loop_store: LoopStore, lifecycle: LoopLifecycle) -> None:
        self._loop_store = loop_store
        self._lifecycle = lifecycle

    async def run(self) -> None:
        for loop in await self._loop_store.list_drift_candidates():
            if not drift.is_drift_eligible(loop):
                continue
            try:
                drifted = await self._lifecycle.drift(loop.id)
            except (InvalidLoopTransitionError, LoopNotFoundError):
                drifted = None
            if drifted is None:
                log.info("open_loop_drift_skipped", loop_id=str(loop.id))
                continue
            log.info("open_loop_drifted_from_sweep", loop_id=str(loop.id))
