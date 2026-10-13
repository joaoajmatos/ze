from __future__ import annotations

from ze_logging import get_logger
from ze_proactive.job import proactive_job
from ze_proactive.notifier import ProactiveNotifier

log = get_logger(__name__)


@proactive_job
class QuietHoursReleaseJob:
    """Sweep: once quiet hours end, release held pushes with one summary buzz."""

    job_id = "quiet_hours_release"

    def __init__(self, notifier: ProactiveNotifier) -> None:
        self._notifier = notifier

    async def run(self) -> None:
        try:
            released = await self._notifier.deliver_held()
        except Exception as exc:
            log.warning("quiet_hours_release_failed", error=str(exc))
            return
        if released:
            log.info("quiet_hours_released", count=released)
