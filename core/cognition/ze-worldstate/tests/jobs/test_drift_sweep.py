from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_worldstate.errors import InvalidLoopTransitionError
from ze_worldstate.jobs import drift_sweep
from ze_worldstate.jobs.drift_sweep import DriftSweepJob
from ze_worldstate.types import LoopClaimKind, LoopProvenance, LoopState, OpenLoop


def _loop(*, deadline_days_from_now: int, state: LoopState = LoopState.ACTIVE) -> OpenLoop:
    return OpenLoop(
        id=uuid4(),
        title="Send Maria the contract",
        claim_kind=LoopClaimKind.PRIORITY,
        provenance=LoopProvenance.USER_DECLARED,
        confidence=0.9,
        state=state,
        drift_deadline=datetime.now(timezone.utc) + timedelta(days=deadline_days_from_now),
    )


def _store(candidates, transition=None) -> AsyncMock:
    store = AsyncMock()
    store.list_drift_candidates = AsyncMock(return_value=candidates)
    store.transition = transition or AsyncMock()
    store.set_drift_rationale = AsyncMock()
    return store


async def test_passed_deadline_drifts():
    loop = _loop(deadline_days_from_now=-1)
    store = _store([loop])

    await DriftSweepJob(loop_store=store).run()

    store.transition.assert_awaited_once_with(loop.id, LoopState.DRIFTING.value)
    store.set_drift_rationale.assert_awaited_once()


async def test_future_deadline_is_left_alone_even_if_returned():
    store = _store([_loop(deadline_days_from_now=2)])
    await DriftSweepJob(loop_store=store).run()
    store.transition.assert_not_awaited()


async def test_non_active_states_untouched():
    store = _store([_loop(deadline_days_from_now=-1, state=LoopState.DRIFTING)])
    await DriftSweepJob(loop_store=store).run()
    store.transition.assert_not_awaited()


async def test_sweep_continues_after_an_invalid_transition():
    first = _loop(deadline_days_from_now=-1)
    second = _loop(deadline_days_from_now=-2)
    store = _store(
        [first, second],
        transition=AsyncMock(side_effect=[InvalidLoopTransitionError("moved"), None]),
    )

    await DriftSweepJob(loop_store=store).run()

    assert store.transition.await_count == 2
    store.set_drift_rationale.assert_awaited_once()
    assert store.set_drift_rationale.await_args.args[0] == second.id


def test_sweep_no_longer_uses_is_stale():
    assert "is_stale" not in inspect.getsource(drift_sweep)
