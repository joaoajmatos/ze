from __future__ import annotations

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
    surfacer.log_push = AsyncMock()

    notifier = AsyncMock()
    notifier.push = AsyncMock()

    job = PushSweepJob(loop_store=loop_store, surfacer=surfacer, notifier=notifier)
    return job, {"loop_store": loop_store, "surfacer": surfacer, "notifier": notifier}


async def test_clears_all_bars_pushes_exactly_once():
    loop = _loop()
    job, mocks = _job([loop], passes=True)

    await job.run()

    mocks["notifier"].push.assert_awaited_once()
    mocks["surfacer"].log_push.assert_awaited_once_with(loop.id, loop.drift_rationale)


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
