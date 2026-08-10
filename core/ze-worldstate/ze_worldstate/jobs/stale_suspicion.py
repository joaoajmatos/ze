from __future__ import annotations

from ze_logging import get_logger
from ze_proactive.staleness import is_stale
from ze_sdk.proactive import proactive_job

from ze_worldstate.store import LoopStore
from ze_worldstate.types import LoopState

log = get_logger(__name__)

DEFAULT_STALE_WINDOW_DAYS = 14


@proactive_job
class StaleSuspicionJob:
    job_id = "worldstate_stale_suspicion_sweep"

    def __init__(
        self, loop_store: LoopStore, window_days: int = DEFAULT_STALE_WINDOW_DAYS
    ) -> None:
        self._loop_store = loop_store
        self._window_days = window_days

    async def run(self) -> None:
        loops = await self._loop_store.list([LoopState.SUSPECTED.value])
        for loop in loops:
            if loop.created_at is not None and is_stale(loop.created_at, self._window_days):
                await self._loop_store.transition(loop.id, LoopState.DROPPED.value)
                log.info("stale_suspicion_dropped", loop_id=str(loop.id))
