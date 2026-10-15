from __future__ import annotations

from datetime import datetime, timedelta, tzinfo

from ze_logging import get_logger
from ze_proactive.errors import CatchUpError

log = get_logger(__name__)

_MAX_STEPS = 10_000


def missed_fire_time(
    cron: str, last_run_at: datetime, now: datetime, tz: tzinfo
) -> datetime | None:
    """Latest cron fire time `t` with `last_run_at < t <= now`, else None."""
    from apscheduler.triggers.cron import CronTrigger

    if last_run_at.tzinfo is None or now.tzinfo is None:
        raise CatchUpError("catch-up needs timezone-aware datetimes")

    trigger = CronTrigger.from_crontab(cron, timezone=tz)
    latest: datetime | None = None
    previous: datetime | None = None
    cursor = last_run_at + timedelta(microseconds=1)
    for _ in range(_MAX_STEPS):
        nxt = trigger.get_next_fire_time(previous, cursor)
        if nxt is None or nxt > now:
            return latest
        latest = nxt
        previous = nxt
        cursor = nxt
    log.warning("catchup_iteration_cap", cron=cron)
    return latest
