from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from ze_priority.arbitration import AttentionArbitrationJob

from tests.factories import make_hypothesis, make_loop


def _push_log(*, count: int = 0, claim_results: list[bool] | None = None) -> MagicMock:
    push_log = MagicMock()
    push_log.count_sent_within_hours = AsyncMock(return_value=count)
    if claim_results is not None:
        push_log.try_claim = AsyncMock(side_effect=claim_results)
    else:
        push_log.try_claim = AsyncMock(return_value=True)
    push_log.release_claim = AsyncMock()
    return push_log


def _loop_surfacer(candidates: list, *, send_result: bool = True) -> MagicMock:
    surfacer = MagicMock()
    surfacer.eligible_candidates = AsyncMock(return_value=candidates)
    surfacer.send = AsyncMock(return_value=send_result)
    return surfacer


def _correlation_source(candidates: list, *, send_result: bool = True) -> MagicMock:
    source = MagicMock()
    source.eligible_candidates = AsyncMock(return_value=candidates)
    source.send = AsyncMock(return_value=send_result)
    return source


def _job(
    *,
    loop_candidates: list | None = None,
    hypothesis_candidates: list | None = None,
    push_log: MagicMock | None = None,
    max_pushes_per_day: int = 3,
    loop_send_result: bool = True,
    hypothesis_send_result: bool = True,
) -> tuple[AttentionArbitrationJob, dict]:
    from ze_priority.view import PriorityView

    loop_surfacer = _loop_surfacer(loop_candidates or [], send_result=loop_send_result)
    correlation_source = _correlation_source(
        hypothesis_candidates or [], send_result=hypothesis_send_result
    )
    priority_view = PriorityView(
        loop_store=AsyncMock(), goal_store=AsyncMock(), hypothesis_store=AsyncMock()
    )
    push_log = push_log or _push_log()

    job = AttentionArbitrationJob(
        priority_view=priority_view,
        loop_surfacer=loop_surfacer,
        correlation_push_source=correlation_source,
        push_log=push_log,
        max_pushes_per_day=max_pushes_per_day,
    )
    return job, {
        "loop_surfacer": loop_surfacer,
        "correlation_push_source": correlation_source,
        "push_log": push_log,
    }


async def test_higher_ranked_candidate_is_sent_with_one_slot_remaining():
    # 10-day-drifting loop outranks a fresh low-confidence hypothesis.
    loop = make_loop(confidence=0.5)
    hyp = make_hypothesis(confidence=0.2, relevance=0.3)
    push_log = _push_log(count=2)  # one slot left of max_pushes_per_day=3
    job, mocks = _job(
        loop_candidates=[loop], hypothesis_candidates=[hyp], push_log=push_log
    )

    await job.run()

    mocks["loop_surfacer"].send.assert_awaited_once_with(loop)
    mocks["correlation_push_source"].send.assert_not_awaited()


async def test_zero_remaining_budget_sends_neither_candidate():
    loop = make_loop(confidence=0.9)
    hyp = make_hypothesis(confidence=0.9, relevance=0.9)
    push_log = _push_log(count=3)  # budget exhausted, max_pushes_per_day=3
    job, mocks = _job(
        loop_candidates=[loop], hypothesis_candidates=[hyp], push_log=push_log
    )

    await job.run()

    mocks["loop_surfacer"].send.assert_not_awaited()
    mocks["correlation_push_source"].send.assert_not_awaited()


async def test_lost_claim_race_falls_through_to_next_ranked_candidate():
    loop = make_loop(confidence=0.9)  # ranks first
    hyp = make_hypothesis(confidence=0.2, relevance=0.3)  # ranks second
    push_log = _push_log(count=0, claim_results=[False, True])
    job, mocks = _job(
        loop_candidates=[loop], hypothesis_candidates=[hyp], push_log=push_log
    )

    await job.run()

    mocks["loop_surfacer"].send.assert_not_awaited()
    mocks["correlation_push_source"].send.assert_awaited_once_with(hyp)


async def test_no_eligible_candidates_sends_nothing():
    job, mocks = _job()
    await job.run()
    mocks["loop_surfacer"].send.assert_not_awaited()
    mocks["correlation_push_source"].send.assert_not_awaited()


async def test_send_failure_releases_claim_and_stops():
    loop = make_loop(confidence=0.9)
    push_log = _push_log(count=0)
    job, mocks = _job(loop_candidates=[loop], push_log=push_log, loop_send_result=False)

    await job.run()

    mocks["loop_surfacer"].send.assert_awaited_once_with(loop)
    push_log.release_claim.assert_awaited_once()


async def test_job_id_is_attention_arbitration_sweep():
    job, _ = _job()
    assert job.job_id == "attention_arbitration_sweep"
