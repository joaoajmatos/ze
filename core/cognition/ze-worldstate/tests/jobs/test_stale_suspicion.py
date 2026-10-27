from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_worldstate.jobs.stale_suspicion import StaleSuspicionJob
from ze_worldstate.lifecycle import LoopLifecycle
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopProvenance, LoopState, OpenLoop


def _loop(age_days: int, state=LoopState.SUSPECTED) -> OpenLoop:
    return OpenLoop(
        id=uuid4(),
        title="Some loop",
        provenance=LoopProvenance.CONVERSATION,
        confidence=0.3,
        state=state,
        created_at=datetime.now(timezone.utc) - timedelta(days=age_days),
    )


def _job(loops) -> tuple[StaleSuspicionJob, AsyncMock, AsyncMock]:
    loop_store = AsyncMock(spec=PostgresLoopStore)
    loop_store.list.return_value = loops
    lifecycle = AsyncMock(spec=LoopLifecycle)
    lifecycle.expire.return_value = object()
    job = StaleSuspicionJob(loop_store=loop_store, lifecycle=lifecycle, window_days=14)
    return job, loop_store, lifecycle


async def test_suspected_loop_older_than_window_is_expired():
    old_loop = _loop(age_days=20)
    job, _, lifecycle = _job([old_loop])

    await job.run()

    lifecycle.expire.assert_awaited_once_with(old_loop.id)


async def test_suspected_loop_within_window_is_untouched():
    job, _, lifecycle = _job([_loop(age_days=2)])
    await job.run()
    lifecycle.expire.assert_not_awaited()


async def test_only_suspected_loops_are_swept():
    job, loop_store, lifecycle = _job([])

    await job.run()

    loop_store.list.assert_awaited_once_with([LoopState.SUSPECTED.value])
    lifecycle.expire.assert_not_awaited()
