from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Awaitable, Callable

from ze_logging import get_logger
from ze_proactive.catchup import missed_fire_time

if TYPE_CHECKING:
    from ze_proactive.job import ProactiveJob
    from ze_proactive.job_run_store import JobRunStore

log = get_logger(__name__)


_CATCH_UP_STAGGER = timedelta(seconds=5)


@dataclass(frozen=True)
class _Registration:
    cron: str
    catch_up: bool
    catch_up_max_age_hours: float | None
    run: Callable[[], Awaitable[None]]


class ProactiveScheduler:
    """Thin wrapper around APScheduler's AsyncIOScheduler.

    With a `run_store`, each cron job's runs are recorded and, on `start()`, a
    job whose scheduled time passed while the process was down runs once."""

    def __init__(
        self,
        run_store: "JobRunStore | None" = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        self._scheduler = AsyncIOScheduler()
        self._started = False
        self._run_store = run_store
        self._clock = clock
        self._registered: dict[str, _Registration] = {}

    def register(
        self,
        job: "ProactiveJob",
        cron: str,
        *,
        catch_up: bool = True,
        catch_up_max_age_hours: float | None = None,
    ) -> None:
        """Register a ProactiveJob instance on a cron schedule."""
        self.add_cron_job(
            fn=job.run,
            cron=cron,
            job_id=job.job_id,
            catch_up=catch_up,
            catch_up_max_age_hours=catch_up_max_age_hours,
        )

    def add_cron_job(
        self,
        fn: Callable[[], Awaitable[None]],
        cron: str,
        job_id: str,
        *,
        catch_up: bool = True,
        catch_up_max_age_hours: float | None = None,
    ) -> None:
        """Register a cron job. Safe to call before or after start()."""
        from apscheduler.triggers.cron import CronTrigger

        run = self._recording(job_id, fn)
        self._scheduler.add_job(
            run,
            trigger=CronTrigger.from_crontab(cron),
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=None,
        )
        self._registered[job_id] = _Registration(
            cron, catch_up, catch_up_max_age_hours, run
        )
        log.info("proactive_job_registered", job_id=job_id, cron=cron)

    def _recording(
        self, job_id: str, fn: Callable[[], Awaitable[None]]
    ) -> Callable[[], Awaitable[None]]:
        store = self._run_store

        async def run() -> None:
            if store is not None:
                await store.record_start(job_id)
            try:
                await fn()
            except BaseException:
                if store is not None:
                    await store.record_finish(job_id, "error")
                raise
            if store is not None:
                await store.record_finish(job_id, "ok")

        run.__name__ = f"proactive_{job_id}"
        return run

    def remove_job(self, job_id: str) -> None:
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
            log.info("proactive_job_removed", job_id=job_id)

    async def start(self) -> None:
        if self._started:
            return
        self._scheduler.start()
        self._started = True
        await self._schedule_catch_ups()
        log.info("proactive_scheduler_started", jobs=len(self._scheduler.get_jobs()))

    async def _schedule_catch_ups(self) -> None:
        if self._run_store is None:
            return
        from apscheduler.triggers.date import DateTrigger

        runs = await self._run_store.get_all()
        now = self._clock()
        tz = self._scheduler.timezone
        scheduled = 0
        for job_id, reg in self._registered.items():
            run = runs.get(job_id)
            if not reg.catch_up or run is None:
                continue
            missed = missed_fire_time(reg.cron, run.last_started_at, now, tz)
            if missed is None:
                continue
            if reg.catch_up_max_age_hours is not None and now - missed > timedelta(
                hours=reg.catch_up_max_age_hours
            ):
                log.info("proactive_job_catch_up_too_old", job_id=job_id)
                continue
            scheduled += 1
            self._scheduler.add_job(
                reg.run,
                trigger=DateTrigger(run_date=now + _CATCH_UP_STAGGER * scheduled),
                id=f"{job_id}:catchup",
                replace_existing=True,
                misfire_grace_time=None,
            )
            log.info(
                "proactive_job_catch_up", job_id=job_id, missed_at=missed.isoformat()
            )

    async def stop(self) -> None:
        if self._started and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self._started = False
            log.info("proactive_scheduler_stopped")

    async def trigger_now(self, fn: Callable[[], Awaitable[None]]) -> None:
        """Run a job function immediately, outside the scheduler."""
        asyncio.create_task(fn())
