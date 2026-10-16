from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from ze_automation.holds.resumer import HeldWriteNotOpenError, HeldWriteResumer
from ze_automation.holds.store import HeldWriteStore
from ze_logging import get_logger
from ze_proactive.job import proactive_job

log = get_logger(__name__)


@proactive_job
class HeldWriteExpiryJob:
    """Resumes held writes nobody answered within 24 hours, as a timeout (FR-025)."""

    job_id = "held_write_expiry"

    def __init__(
        self,
        held_store: HeldWriteStore,
        resumer: HeldWriteResumer,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._store = held_store
        self._resumer = resumer
        self._clock = clock

    async def run(self) -> None:
        expired = await self._store.list_expired(self._clock())
        for hold in expired:
            try:
                claimed = await self._resumer.decide(hold.request_id, "timeout")
            except HeldWriteNotOpenError:
                continue
            await self._resumer.run(claimed, "timeout")
            log.info("held_write_expired", request_id=hold.request_id)
