from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_worldstate.jobs.drift_sweep import DriftSweepJob
from ze_worldstate.types import LoopClaimKind, LoopProvenance, LoopState, OpenLoop


def _loop(*, confirmed_days_ago: int, updated_days_ago: int, window_days: int = 7) -> OpenLoop:
    now = datetime.now(timezone.utc)
    confirmed_at = now - timedelta(days=confirmed_days_ago)
    return OpenLoop(
        id=uuid4(),
        title="Send Maria the contract",
        claim_kind=LoopClaimKind.PRIORITY,
        provenance=LoopProvenance.USER_DECLARED,
        confidence=0.9,
        state=LoopState.ACTIVE,
        confirmed_at=confirmed_at,
        updated_at=now - timedelta(days=updated_days_ago),
        drift_deadline=confirmed_at + timedelta(days=window_days),
    )


async def test_elapsed_window_no_evidence_drifts():
    loop = _loop(confirmed_days_ago=10, updated_days_ago=10)
    loop_store = AsyncMock()
    loop_store.list_drift_candidates = AsyncMock(return_value=[loop])
    loop_store.transition = AsyncMock()
    loop_store.set_drift_rationale = AsyncMock()

    job = DriftSweepJob(loop_store=loop_store)
    await job.run()

    loop_store.transition.assert_awaited_once_with(loop.id, LoopState.DRIFTING.value)
    loop_store.set_drift_rationale.assert_awaited_once()


async def test_fresh_evidence_stays_active():
    loop = _loop(confirmed_days_ago=10, updated_days_ago=0)
    loop_store = AsyncMock()
    loop_store.list_drift_candidates = AsyncMock(return_value=[loop])
    loop_store.transition = AsyncMock()
    loop_store.set_drift_rationale = AsyncMock()

    job = DriftSweepJob(loop_store=loop_store)
    await job.run()

    loop_store.transition.assert_not_awaited()
    loop_store.set_drift_rationale.assert_not_awaited()


async def test_non_active_states_untouched():
    loop = _loop(confirmed_days_ago=10, updated_days_ago=10)
    loop.state = LoopState.DRIFTING
    loop_store = AsyncMock()
    loop_store.list_drift_candidates = AsyncMock(return_value=[loop])
    loop_store.transition = AsyncMock()
    loop_store.set_drift_rationale = AsyncMock()

    job = DriftSweepJob(loop_store=loop_store)
    await job.run()

    loop_store.transition.assert_not_awaited()


async def test_transient_failure_mid_batch_leaves_processed_transitions_intact():
    loop_ok = _loop(confirmed_days_ago=10, updated_days_ago=10)
    loop_fails = _loop(confirmed_days_ago=10, updated_days_ago=10)
    loop_store = AsyncMock()
    loop_store.list_drift_candidates = AsyncMock(return_value=[loop_ok, loop_fails])
    loop_store.transition = AsyncMock(side_effect=[None, RuntimeError("boom")])
    loop_store.set_drift_rationale = AsyncMock()

    job = DriftSweepJob(loop_store=loop_store)
    try:
        await job.run()
    except RuntimeError:
        pass

    assert loop_store.transition.await_count == 2
    loop_store.transition.assert_any_await(loop_ok.id, LoopState.DRIFTING.value)
