from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_priority.arbitration import AttentionArbitrationJob
from ze_priority.types import PriorityOverride
from ze_priority.view import PriorityView
from ze_worldstate.bootstrap import LoopPushSettings

from ze_worldstate.types import LoopState

from tests.factories import make_hypothesis, make_loop

UTC = timezone.utc


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
    loop_push: LoopPushSettings | None = None,
    overrides: list | None = None,
    loop_store: AsyncMock | None = None,
) -> tuple[AttentionArbitrationJob, dict]:
    loop_surfacer = _loop_surfacer(loop_candidates or [], outcome=loop_outcome)
    correlation_source = _correlation_source(
        hypothesis_candidates or [], outcome=hypothesis_outcome
    )
    override_store = None
    if overrides is not None:
        override_store = AsyncMock()
        override_store.get_active.return_value = overrides
    priority_view = PriorityView(
        loop_store=loop_store or AsyncMock(),
        goal_store=AsyncMock(),
        hypothesis_store=AsyncMock(),
        override_store=override_store,
    )
    notifier = _notifier(remaining=remaining)

    job = AttentionArbitrationJob(
        priority_view=priority_view,
        loop_surfacer=loop_surfacer,
        correlation_push_source=correlation_source,
        notifier=notifier,
        loop_push=loop_push,
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
    job, mocks = _job(loop_candidates=[loop], hypothesis_candidates=[hyp], remaining=0)

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


# ── loop push switch (phase 170 US5) ─────────────────────────────────────────


async def test_disabled_loop_push_never_queries_the_surfacer():
    loop = make_loop(confidence=0.9)
    hyp = make_hypothesis(confidence=0.9, relevance=0.9)
    job, mocks = _job(
        loop_candidates=[loop],
        hypothesis_candidates=[hyp],
        loop_push=LoopPushSettings(enabled=False),
    )

    await job.run()

    mocks["loop_surfacer"].eligible_candidates.assert_not_awaited()
    mocks["correlation_push_source"].send.assert_awaited_once_with(hyp)


async def test_loop_push_settings_are_forwarded_to_eligible_candidates():
    loop = make_loop(confidence=0.9)
    settings = LoopPushSettings(
        enabled=True,
        thresholds={"tau_confidence": 0.7},
        inline_cooldown_hours=6.0,
    )
    job, mocks = _job(loop_candidates=[loop], loop_push=settings)

    await job.run()

    mocks["loop_surfacer"].eligible_candidates.assert_awaited_once_with(
        thresholds={"tau_confidence": 0.7},
        inline_cooldown_hours=6.0,
    )
    mocks["loop_surfacer"].send.assert_awaited_once_with(loop)


async def test_default_loop_push_uses_enabled_defaults():
    loop = make_loop(confidence=0.9)
    job, mocks = _job(loop_candidates=[loop])

    await job.run()

    mocks["loop_surfacer"].eligible_candidates.assert_awaited_once_with(
        thresholds={},
        inline_cooldown_hours=12.0,
    )


# ── the user's order (phase 198, B5) ─────────────────────────────────────────


def _active_loops():
    """A computes higher than B; both are in the full ranking."""
    a = make_loop(title="A", confidence=0.9, state=LoopState.ACTIVE)
    b = make_loop(title="B", confidence=0.2, state=LoopState.ACTIVE)
    loop_store = AsyncMock()
    loop_store.list.return_value = [a, b]
    return a, b, loop_store


def _override(item, anchor, relation, *, pinned=True, age_hours=0.0):
    return PriorityOverride(
        id=uuid4(),
        source_kind="loop",
        source_id=item.id,
        anchor_source_kind="loop",
        anchor_source_id=anchor.id,
        relation=relation,
        pinned=pinned,
        submitted_at=datetime.now(UTC) - timedelta(hours=age_hours),
        superseded_at=None,
        contribution_domain_id=uuid4(),
    )


async def test_user_order_decides_which_candidate_is_sent_first():
    a, b, loop_store = _active_loops()
    job, mocks = _job(
        loop_candidates=[a, b],
        overrides=[_override(b, a, "above")],
        loop_store=loop_store,
    )

    await job.run()

    mocks["loop_surfacer"].send.assert_awaited_once_with(b)


async def test_an_item_the_user_pushed_down_is_never_sent_even_when_alone():
    a, b, loop_store = _active_loops()
    job, mocks = _job(
        loop_candidates=[a],
        overrides=[_override(a, b, "below")],
        loop_store=loop_store,
    )

    await job.run()

    mocks["loop_surfacer"].send.assert_not_awaited()


async def test_a_pushed_down_item_does_not_block_the_next_candidate():
    a, b, loop_store = _active_loops()
    job, mocks = _job(
        loop_candidates=[a, b],
        overrides=[_override(a, b, "below")],
        loop_store=loop_store,
    )

    await job.run()

    mocks["loop_surfacer"].send.assert_awaited_once_with(b)


async def test_zero_budget_with_pins_sends_nothing():
    a, b, loop_store = _active_loops()
    job, mocks = _job(
        loop_candidates=[a, b],
        overrides=[_override(b, a, "above")],
        loop_store=loop_store,
        remaining=0,
    )

    await job.run()

    mocks["loop_surfacer"].send.assert_not_awaited()


async def test_a_decayed_override_does_not_exclude_its_item():
    a, b, loop_store = _active_loops()
    job, mocks = _job(
        loop_candidates=[a],
        overrides=[_override(a, b, "below", pinned=False, age_hours=72)],
        loop_store=loop_store,
    )

    await job.run()

    mocks["loop_surfacer"].send.assert_awaited_once_with(a)


# ── the push bar holds through the job (phase 198, B4, SC-006) ───────────────


class _Nli:
    def __init__(self, score: float) -> None:
        self._score = score

    async def scores(self, pairs):
        return [self._score] * len(pairs)

    def grounding_score(self, summary, labels, scores=None):
        return max(scores) if scores else 0.0


class _PushLog:
    def __init__(self, rows: list[tuple[str, str, float]] | None = None) -> None:
        self._rows = rows or []

    async def list_recent_payloads(self, event_type, hours):
        return [p for e, p, age in self._rows if e == event_type and age < hours]

    async def was_sent_within_hours(self, event_type, hours):
        return False


class _Embedder:
    def encode_passage(self, text):
        import numpy as np

        vec = np.zeros(64)
        for word in text.lower().split():
            vec[hash(word) % 64] += 1.0
        return vec


def _real_surfacer_job(monkeypatch, loop, *, nli_score, push_rows=None):
    from ze_worldstate import surfacing
    from ze_worldstate.surfacing import LoopSurfacer

    async def evidence(pool, loop_store, loop_id):
        return [{"type": "episode", "id": uuid4(), "summary": "I need to send it"}]

    monkeypatch.setattr(surfacing, "_fetch_evidence_summaries", evidence)
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[loop])
    loop_store.get = AsyncMock(return_value=loop)
    relevance = MagicMock()
    relevance.build = AsyncMock(return_value=object())
    relevance.score = MagicMock(return_value=MagicMock(value=0.9))
    notifier = MagicMock()
    notifier.remaining_budget = AsyncMock(return_value=3)
    notifier.notify = AsyncMock(return_value="delivered")
    surfacer = LoopSurfacer(
        loop_store=loop_store,
        graph_store=AsyncMock(),
        push_log=_PushLog(push_rows),
        relevance_model=relevance,
        embedder=_Embedder(),
        notifier=notifier,
        nli_client=_Nli(nli_score),
    )
    correlation = MagicMock()
    correlation.eligible_candidates = AsyncMock(return_value=[])
    job = AttentionArbitrationJob(
        priority_view=PriorityView(
            loop_store=loop_store, goal_store=AsyncMock(), hypothesis_store=AsyncMock()
        ),
        loop_surfacer=surfacer,
        correlation_push_source=correlation,
        notifier=notifier,
    )
    return job, notifier


async def test_job_sends_nothing_for_a_loop_its_evidence_does_not_support(monkeypatch):
    loop = make_loop(confidence=0.9)
    job, notifier = _real_surfacer_job(monkeypatch, loop, nli_score=0.01)

    await job.run()

    notifier.notify.assert_not_awaited()


async def test_job_sends_nothing_for_a_loop_it_pushed_a_moment_ago(monkeypatch):
    from ze_worldstate.surfacing import format_hedged_mention

    loop = make_loop(confidence=0.9)
    repeated = format_hedged_mention(loop.title, loop.drift_rationale)
    job, notifier = _real_surfacer_job(
        monkeypatch, loop, nli_score=0.9, push_rows=[("attention_push", repeated, 3.0)]
    )

    await job.run()

    notifier.notify.assert_not_awaited()


async def test_job_sends_a_grounded_fresh_loop(monkeypatch):
    loop = make_loop(confidence=0.9)
    job, notifier = _real_surfacer_job(monkeypatch, loop, nli_score=0.9)

    await job.run()

    notifier.notify.assert_awaited_once()
