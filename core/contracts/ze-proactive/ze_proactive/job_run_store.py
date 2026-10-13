from __future__ import annotations

from typing import Literal

import asyncpg

from ze_logging import get_logger
from ze_proactive.types import JobRun

log = get_logger(__name__)


class JobRunStore:
    """Best-effort record of each proactive job's last run, for catch-up. Store
    errors are logged and swallowed: a job never fails because its run could
    not be recorded."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def record_start(self, job_id: str) -> None:
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO proactive_job_runs
                        (job_id, last_started_at, last_finished_at, last_status)
                    VALUES ($1, NOW(), NULL, 'running')
                    ON CONFLICT (job_id) DO UPDATE SET
                        last_started_at = NOW(),
                        last_finished_at = NULL,
                        last_status = 'running'
                    """,
                    job_id,
                )
        except Exception as exc:
            log.warning("job_run_record_start_failed", job_id=job_id, error=str(exc))

    async def record_finish(self, job_id: str, status: Literal["ok", "error"]) -> None:
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    "UPDATE proactive_job_runs "
                    "SET last_finished_at = NOW(), last_status = $2 WHERE job_id = $1",
                    job_id,
                    status,
                )
        except Exception as exc:
            log.warning("job_run_record_finish_failed", job_id=job_id, error=str(exc))

    async def get_all(self) -> dict[str, JobRun]:
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT job_id, last_started_at, last_finished_at, last_status "
                    "FROM proactive_job_runs"
                )
        except Exception as exc:
            log.warning("job_run_get_all_failed", error=str(exc))
            return {}
        return {
            r["job_id"]: JobRun(
                job_id=r["job_id"],
                last_started_at=r["last_started_at"],
                last_finished_at=r["last_finished_at"],
                last_status=r["last_status"],
            )
            for r in rows
        }
