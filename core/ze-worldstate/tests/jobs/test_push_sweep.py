from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_worldstate.jobs.push_sweep import PushSweepJob
from ze_worldstate.types import LoopClaimKind, LoopProvenance, LoopState, OpenLoop


def _loop(**overrides) -> OpenLoop:
    base = dict(
        id=uuid4(),
        title="Send Maria the contract",
        claim_kind=LoopClaimKind.PRIORITY,
        provenance=LoopProvenance.USER_DECLARED,
        confidence=0.8,
        state=LoopState.DRIFTING,
        drift_rationale="No corroborating evidence since confirmation.",
    )
    base.update(overrides)
    return OpenLoop(**base)


def _job(
    loops: list[OpenLoop],
    *,
    passes: bool = True,
    current_state: LoopState | None = None,
) -> tuple[PushSweepJob, dict]:
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=loops)
    if current_state is not None and loops:
        current_loop = _loop(id=loops[0].id, state=current_state)
        loop_store.get = AsyncMock(return_value=current_loop)
    elif loops:
        loop_store.get = AsyncMock(return_value=loops[0])

    surfacer = AsyncMock()
    surfacer.passes_push_bar = AsyncMock(return_value=passes)
    surfacer.claim_push = AsyncMock(return_value=True)
    surfacer.release_push_claim = AsyncMock()

    notifier = AsyncMock()
    notifier.push = AsyncMock()

    job = PushSweepJob(loop_store=loop_store, surfacer=surfacer, notifier=notifier)
    return job, {"loop_store": loop_store, "surfacer": surfacer, "notifier": notifier}


async def test_clears_all_bars_pushes_exactly_once():
    loop = _loop()
    job, mocks = _job([loop], passes=True)

    await job.run()

    mocks["notifier"].push.assert_awaited_once()
    mocks["surfacer"].claim_push.assert_awaited_once_with(loop.id, loop.drift_rationale)


async def test_failing_push_bar_produces_no_push():
    loop = _loop()
    job, mocks = _job([loop], passes=False)

    await job.run()

    mocks["notifier"].push.assert_not_awaited()


async def test_no_rationale_skips_loop():
    loop = _loop(drift_rationale=None)
    job, mocks = _job([loop], passes=True)

    await job.run()

    mocks["surfacer"].passes_push_bar.assert_not_awaited()
    mocks["notifier"].push.assert_not_awaited()


async def test_loop_closed_between_selection_and_send_gets_no_push():
    """FR-011: re-check current lifecycle state immediately before sending."""
    loop = _loop()
    job, mocks = _job([loop], passes=True, current_state=LoopState.CLOSED)

    await job.run()

    mocks["notifier"].push.assert_not_awaited()


async def test_loop_deleted_between_selection_and_send_gets_no_push():
    loop = _loop()
    job, mocks = _job([loop], passes=True)
    mocks["loop_store"].get = AsyncMock(return_value=None)

    await job.run()

    mocks["notifier"].push.assert_not_awaited()


async def test_already_claimed_push_is_skipped_not_errored():
    loop = _loop()
    job, mocks = _job([loop], passes=True)
    mocks["surfacer"].claim_push = AsyncMock(return_value=False)

    await job.run()  # must not raise

    mocks["notifier"].push.assert_not_awaited()


async def test_concurrent_sweeps_on_same_loop_push_exactly_once():
    """Two concurrent PushSweepJob.run() calls against a loop that qualifies for
    exactly one push must result in exactly one notifier.push() call total —
    the DB claim (mocked here as a shared, mutually-exclusive gate), not the
    pre-check, is the arbiter of exclusivity."""
    loop = _loop()
    job_a, mocks_a = _job([loop], passes=True)
    job_b, mocks_b = _job([loop], passes=True)

    claimed_ids: set = set()

    async def _shared_claim(loop_id, rationale):
        if loop_id in claimed_ids:
            return False
        claimed_ids.add(loop_id)
        return True

    mocks_a["surfacer"].claim_push = AsyncMock(side_effect=_shared_claim)
    mocks_b["surfacer"].claim_push = AsyncMock(side_effect=_shared_claim)

    await asyncio.gather(job_a.run(), job_b.run())

    total_pushes = (
        mocks_a["notifier"].push.await_count + mocks_b["notifier"].push.await_count
    )
    assert total_pushes == 1


async def test_notifier_failure_after_claim_rolls_back_claim():
    """(remediation for analysis finding G1) A notifier failure after a
    successful claim must release the claim so a future sweep can retry, and
    must not abort processing of other loops in the same sweep."""
    loop_a = _loop()
    loop_b = _loop()
    job, mocks = _job([loop_a, loop_b], passes=True)
    mocks["loop_store"].get = AsyncMock(side_effect=[loop_a, loop_b])
    mocks["notifier"].push = AsyncMock(
        side_effect=[RuntimeError("ntfy down"), None]
    )

    await job.run()  # must not raise

    mocks["surfacer"].release_push_claim.assert_awaited_once_with(loop_a.id)
    assert mocks["notifier"].push.await_count == 2
