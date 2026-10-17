from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from ze_api.api.deps import get_job_run_store, require_api_key
from ze_api.api.v0.proactive.schemas import ProactiveJobRunItem
from ze_logging import get_logger

log = get_logger(__name__)

router = APIRouter(
    prefix="/proactive",
    tags=["proactive"],
    dependencies=[Depends(require_api_key)],
)


@router.get(
    "/job-runs",
    response_model=list[ProactiveJobRunItem],
    operation_id="listProactiveJobRuns",
    summary="List the last run of each proactive job",
    description=(
        "One row per proactive job with its last start, finish and status "
        "(running, ok or error), newest first. This is the last run only, not a "
        "history. Use since to keep jobs that started at or after a time. Returns "
        "503 when the run store cannot be read."
    ),
)
async def list_proactive_job_runs(
    since: datetime | None = Query(
        default=None, description="Only jobs whose last run started at or after this time."
    ),
    store=Depends(get_job_run_store),
) -> list[ProactiveJobRunItem]:
    try:
        runs = await store.list_runs()
    except Exception as exc:
        log.warning("proactive_job_runs_unavailable", error=str(exc))
        raise HTTPException(status_code=503, detail="Job runs unavailable") from exc
    if since is not None:
        runs = [r for r in runs if r.last_started_at >= since]
    runs = sorted(runs, key=lambda r: r.last_started_at, reverse=True)
    return [
        ProactiveJobRunItem(
            job_id=r.job_id,
            last_started_at=r.last_started_at,
            last_finished_at=r.last_finished_at,
            last_status=r.last_status,
        )
        for r in runs
    ]
