from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from ze_priority.arbitration import AttentionArbitrationJob

from tests.factories import make_hypothesis, make_loop


def _notifier(*, remaining: int = 3) -> MagicMock:
    notifier = MagicMock()
    notifier.remaining_budget = AsyncMock(return_value=remaining)
    return notifier


def _loop_surfacer(candidates: list, *, outcome="delivered") -> MagicMock:
    surfacer = MagicMock()
    surfacer.eligible_candidates = AsyncMock(return_value=candidates)
    surfacer.send = AsyncMock(return_value=outcome)
    return surfacer


def _correlation_source(candidates: list, *, outcome="delivered") -> MagicMock:
    source = MagicMock()
    source.eligible_candidates = AsyncMock(return_value=candidates)
    source.send = AsyncMock(return_value=outcome)
    return source


def _job(
    *,
    loop_candidates: list | None = None,
    hypothesis_candidates: list | None = None,
    remaining: int = 3,
    loop_outcome="delivered",
    hypothesis_outcome="delivered",
) -> tuple[AttentionArbitrationJob, dict]:
    from ze_priority.view import PriorityView

    loop_surfacer = _loop_surfacer(loop_candidates or [], outcome=loop_outcome)
    correlation_source = _correlation_source(
        hypothesis_candidates or [], outcome=hypothesis_outcome
    )
    priority_view = PriorityView(
        loop_store=AsyncMock(), goal_store=AsyncMock(), hypothesis_store=AsyncMock()
    )
    notifier = _notifier(remaining=remaining)

    job = AttentionArbitrationJob(
        priority_view=priority_view,
        loop_surfacer=loop_surfacer,
        correlation_push_source=correlation_source,
        notifier=notifier,
    )
    return job, {
        "loop_surfacer": loop_surfacer,
        "correlation_push_source": correlation_source,
        "notifier": notifier,
    }


async def test_top_ranked_candidate_delivered_stops_the_sweep():
    # 10-day-drifting loop outranks a fresh low-confidence hypothesis.
    loop = make_loop(confidence=0.5)
    hyp = make_hypothesis(confidence=0.2, relevance=0.3)
    job, mocks = _job(loop_candidates=[loop], hypothesis_candidates=[hyp])

    await job.run()

    mocks["loop_surfacer"].send.assert_awaited_once_with(loop)
    mocks["correlation_push_source"].send.assert_not_awaited()


async def test_zero_remaining_budget_sends_nothing():
    loop = make_loop(confidence=0.9)
    hyp = make_hypothesis(confidence=0.9, relevance=0.9)
    job, mocks = _job(
        loop_candidates=[loop], hypothesis_candidates=[hyp], remaining=0
    )

    await job.run()

    mocks["loop_surfacer"].send.assert_not_awaited()
    mocks["correlation_push_source"].send.assert_not_awaited()


async def test_duplicate_falls_through_to_next_ranked_candidate():
    loop = make_loop(confidence=0.9)  # ranks first
    hyp = make_hypothesis(confidence=0.2, relevance=0.3)  # ranks second
    job, mocks = _job(
        loop_candidates=[loop],
        hypothesis_candidates=[hyp],
        loop_outcome="duplicate",
    )

    await job.run()

    mocks["loop_surfacer"].send.assert_awaited_once_with(loop)
    mocks["correlation_push_source"].send.assert_awaited_once_with(hyp)


async def test_none_outcome_loop_no_longer_drifting_falls_through():
    loop = make_loop(confidence=0.9)
    hyp = make_hypothesis(confidence=0.2, relevance=0.3)
    job, mocks = _job(
        loop_candidates=[loop], hypothesis_candidates=[hyp], loop_outcome=None
    )

    await job.run()

    mocks["correlation_push_source"].send.assert_awaited_once_with(hyp)


async def test_suppressed_budget_stops_the_sweep():
    loop = make_loop(confidence=0.9)
    hyp = make_hypothesis(confidence=0.2, relevance=0.3)
    job, mocks = _job(
        loop_candidates=[loop],
        hypothesis_candidates=[hyp],
        loop_outcome="suppressed_budget",
    )

    await job.run()

    mocks["correlation_push_source"].send.assert_not_awaited()


async def test_held_counts_as_sent():
    loop = make_loop(confidence=0.9)
    hyp = make_hypothesis(confidence=0.2, relevance=0.3)
    job, mocks = _job(
        loop_candidates=[loop], hypothesis_candidates=[hyp], loop_outcome="held"
    )

    await job.run()

    mocks["correlation_push_source"].send.assert_not_awaited()


async def test_failed_send_continues_to_next_candidate():
    loop = make_loop(confidence=0.9)
    hyp = make_hypothesis(confidence=0.2, relevance=0.3)
    job, mocks = _job(
        loop_candidates=[loop], hypothesis_candidates=[hyp], loop_outcome="failed"
    )

    await job.run()

    mocks["correlation_push_source"].send.assert_awaited_once_with(hyp)


async def test_no_eligible_candidates_sends_nothing():
    job, mocks = _job()
    await job.run()
    mocks["loop_surfacer"].send.assert_not_awaited()
    mocks["correlation_push_source"].send.assert_not_awaited()


async def test_job_id_is_attention_arbitration_sweep():
    job, _ = _job()
    assert job.job_id == "attention_arbitration_sweep"
