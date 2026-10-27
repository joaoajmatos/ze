from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_worldstate.errors import InvalidLoopTransitionError
from ze_worldstate.jobs import drift_sweep
from ze_worldstate.jobs.drift_sweep import DriftSweepJob
from ze_worldstate.lifecycle import LoopLifecycle
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopProvenance, LoopState, OpenLoop


def _loop(*, deadline_days_from_now: int, state: LoopState = LoopState.ACTIVE) -> OpenLoop:
    return OpenLoop(
        id=uuid4(),
        title="Send Maria the contract",
        provenance=LoopProvenance.USER_DECLARED,
        confidence=0.9,
        state=state,
        drift_deadline=datetime.now(timezone.utc) + timedelta(days=deadline_days_from_now),
    )


def _job(candidates, drift=None) -> tuple[DriftSweepJob, AsyncMock]:
    store = AsyncMock(spec=PostgresLoopStore)
    store.list_drift_candidates.return_value = candidates
    lifecycle = AsyncMock(spec=LoopLifecycle)
    lifecycle.drift = drift or AsyncMock(return_value=object())
    return DriftSweepJob(loop_store=store, lifecycle=lifecycle), lifecycle


async def test_passed_deadline_drifts():
    loop = _loop(deadline_days_from_now=-1)
    job, lifecycle = _job([loop])

    await job.run()

    lifecycle.drift.assert_awaited_once_with(loop.id)


async def test_future_deadline_is_left_alone_even_if_returned():
    job, lifecycle = _job([_loop(deadline_days_from_now=2)])
    await job.run()
    lifecycle.drift.assert_not_awaited()


async def test_non_active_states_untouched():
    job, lifecycle = _job([_loop(deadline_days_from_now=-1, state=LoopState.DRIFTING)])
    await job.run()
    lifecycle.drift.assert_not_awaited()


async def test_sweep_continues_after_a_refused_or_raced_drift():
    first = _loop(deadline_days_from_now=-1)
    second = _loop(deadline_days_from_now=-2)
    third = _loop(deadline_days_from_now=-3)
    job, lifecycle = _job(
        [first, second, third],
        drift=AsyncMock(
            side_effect=[InvalidLoopTransitionError("moved"), None, object()]
        ),
    )

    await job.run()

    assert [c.args[0] for c in lifecycle.drift.await_args_list] == [
        first.id,
        second.id,
        third.id,
    ]


def test_sweep_no_longer_uses_is_stale():
    assert "is_stale" not in inspect.getsource(drift_sweep)
