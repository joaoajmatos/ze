from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import numpy as np
from structlog.testing import capture_logs
from ze_proactive.candidates import BarThresholds, PushCandidate
from ze_proactive.notifier import ProactiveNotifier
from ze_proactive.testing import InMemoryPushLog
from ze_proactive.types import NotificationRow, OncePer
from ze_worldstate.bootstrap import LoopPushSettings
from ze_worldstate.surfacing import LoopSurfacer, format_hedged_mention
from ze_worldstate.types import LoopState

from ze_priority.arbitration import AttentionArbitrationJob
from ze_priority.push_bar import PushBar
from ze_priority.types import PriorityOverride
from ze_priority.view import PriorityView
from tests.factories import make_hypothesis, make_loop, make_stuck_goal

UTC = timezone.utc

THRESHOLDS = BarThresholds(
    confidence=0.0,
    relevance=0.0,
    novelty_similarity_max=0.9,
    grounding=0.5,
    inline_cooldown_hours=12.0,
)


# ── fakes ────────────────────────────────────────────────────────────────────


class FakeEmbedder:
    """A body maps to a fixed vector; unknown bodies are orthogonal to all."""

    def __init__(self, vectors: dict[str, list[float]] | None = None) -> None:
        self._vectors = vectors or {}
        self._axes: dict[str, int] = {}
        self.encoded: list[str] = []

    def encode_passage(self, text: str) -> np.ndarray:
        self.encoded.append(text)
        if text in self._vectors:
            return np.array(self._vectors[text], dtype=float)
        # each unknown body gets its own axis, so unknown bodies never match
        axis = self._axes.setdefault(text, len(self._axes))
        vec = np.zeros(64)
        vec[2 + axis] = 1.0
        return vec


class FakeNLI:
    def __init__(self, grounded_by_claim: dict[str, float] | None = None) -> None:
        self._grounded = grounded_by_claim or {}
        self.calls = 0

    async def scores(self, pairs):
        self.calls += 1
        return [{"entailment": 1.0} for _ in pairs]

    def grounding_score(self, hypothesis, evidence_texts, scores=None):
        return self._grounded.get(hypothesis, 1.0)

    def pair_is_scorable(self, premise, hypothesis):
        return True


class FakeHistory:
    def __init__(self, bodies: list[str] | None = None) -> None:
        self.bodies = bodies or []

    async def recent_discretionary_bodies(self, hours: float) -> list[str]:
        return list(self.bodies)


class FakeMentions:
    def __init__(self, mentioned_ids: set | None = None) -> None:
        self.mentioned_ids = mentioned_ids or set()

    async def mentioned_inline_within(self, source_kind, source_id, hours) -> bool:
        return source_id in self.mentioned_ids


def _bar(
    *,
    embedder: FakeEmbedder | None = None,
    nli: FakeNLI | None = None,
    history: FakeHistory | None = None,
    mentions: FakeMentions | None = None,
) -> PushBar:
    return PushBar(
        embedder=embedder or FakeEmbedder(),
        nli=nli or FakeNLI(),
        history=history or FakeHistory(),
        mentions=mentions or FakeMentions(),
    )


def _thunk(value):
    async def thunk():
        return value

    return thunk


def _candidate(
    kind: str,
    entity,
    source_id,
    *,
    body: str = "a push body",
    claim: str = "a claim",
    confidence: float = 0.9,
    labels: tuple[str, ...] = ("evidence",),
    once_per: OncePer | None = None,
) -> PushCandidate:
    return PushCandidate(
        source_kind=kind,
        source_id=source_id,
        entity=entity,
        body=body,
        claim=claim,
        confidence=confidence,
        relevance=_thunk(0.9),
        evidence_labels=_thunk(labels),
        once_per=once_per or OncePer(f"{kind}:{source_id}"),
    )


def _loop_candidate(loop, **kw) -> PushCandidate:
    kw.setdefault("claim", loop.title)
    kw.setdefault("body", format_hedged_mention(loop.title, loop.drift_rationale))
    return _candidate("loop", loop, loop.id, **kw)


def _hypothesis_candidate(hyp, **kw) -> PushCandidate:
    kw.setdefault("claim", hyp.summary)
    kw.setdefault("body", f"{hyp.summary}\n\n{hyp.narrative}")
    return _candidate("hypothesis", hyp, hyp.id, **kw)


def _goal_candidate(stuck, **kw) -> PushCandidate:
    return _candidate("goal", stuck, stuck.goal.id, **kw)


class FakeSource:
    def __init__(
        self,
        kind: str,
        candidates: list[PushCandidate],
        *,
        outcome="delivered",
        dry_run: bool = False,
        thresholds: BarThresholds = THRESHOLDS,
    ) -> None:
        self.source_kind = kind
        self.thresholds = thresholds
        self.dry_run = dry_run
        self.candidates = AsyncMock(return_value=candidates)
        self.send = AsyncMock(return_value=outcome)


def _notifier(*, remaining: int = 3, cooling: set | None = None) -> MagicMock:
    notifier = MagicMock()
    notifier.remaining_budget = AsyncMock(return_value=remaining)
    cooling_keys = cooling or set()
    notifier.on_cooldown = AsyncMock(
        side_effect=lambda once_per: once_per.key in cooling_keys
    )
    return notifier


def _view(*, overrides: list | None = None, loop_store=None) -> PriorityView:
    override_store = None
    if overrides is not None:
        override_store = AsyncMock()
        override_store.get_active.return_value = overrides
    return PriorityView(
        loop_store=loop_store or AsyncMock(),
        goal_store=AsyncMock(),
        hypothesis_store=AsyncMock(),
        override_store=override_store,
    )


def _job(
    sources: list[FakeSource],
    *,
    bar: PushBar | None = None,
    notifier: MagicMock | None = None,
    view: PriorityView | None = None,
) -> tuple[AttentionArbitrationJob, MagicMock]:
    notifier = notifier or _notifier()
    job = AttentionArbitrationJob(
        priority_view=view or _view(),
        sources=sources,
        bar=bar or _bar(),
        notifier=notifier,
    )
    return job, notifier


def _loop_and_hypothesis(
    *, loop_outcome="delivered", hyp_outcome="delivered"
) -> tuple[FakeSource, FakeSource, PushCandidate, PushCandidate]:
    loop = make_loop(confidence=0.9)  # a 10-day-drifting loop ranks first
    hyp = make_hypothesis(confidence=0.2, relevance=0.3)
    loop_c, hyp_c = _loop_candidate(loop), _hypothesis_candidate(hyp)
    return (
        FakeSource("loop", [loop_c], outcome=loop_outcome),
        FakeSource("hypothesis", [hyp_c], outcome=hyp_outcome),
        loop_c,
        hyp_c,
    )


# ── ranking and send flow ────────────────────────────────────────────────────


async def test_top_ranked_candidate_delivered_stops_the_sweep():
    loop_source, hyp_source, loop_c, _ = _loop_and_hypothesis()
    job, _ = _job([loop_source, hyp_source])

    await job.run()

    loop_source.send.assert_awaited_once_with(loop_c)
    hyp_source.send.assert_not_awaited()


async def test_zero_remaining_budget_reads_no_candidates():
    loop_source, hyp_source, _, _ = _loop_and_hypothesis()
    job, _ = _job([loop_source, hyp_source], notifier=_notifier(remaining=0))

    await job.run()

    loop_source.candidates.assert_not_awaited()
    hyp_source.candidates.assert_not_awaited()
    loop_source.send.assert_not_awaited()


async def test_deduped_falls_through_to_next_ranked_candidate():
    loop_source, hyp_source, _, hyp_c = _loop_and_hypothesis(loop_outcome="deduped")
    job, _ = _job([loop_source, hyp_source])

    await job.run()

    loop_source.send.assert_awaited_once()
    hyp_source.send.assert_awaited_once_with(hyp_c)


async def test_none_outcome_falls_through():
    loop_source, hyp_source, _, hyp_c = _loop_and_hypothesis(loop_outcome=None)
    job, _ = _job([loop_source, hyp_source])

    await job.run()

    hyp_source.send.assert_awaited_once_with(hyp_c)


async def test_failed_send_continues_to_next_candidate():
    loop_source, hyp_source, _, hyp_c = _loop_and_hypothesis(loop_outcome="failed")
    job, _ = _job([loop_source, hyp_source])

    await job.run()

    hyp_source.send.assert_awaited_once_with(hyp_c)


async def test_suppressed_budget_stops_the_sweep():
    loop_source, hyp_source, _, _ = _loop_and_hypothesis(
        loop_outcome="suppressed_budget"
    )
    job, _ = _job([loop_source, hyp_source])

    await job.run()

    hyp_source.send.assert_not_awaited()


async def test_held_counts_as_sent():
    loop_source, hyp_source, _, _ = _loop_and_hypothesis(loop_outcome="held")
    job, _ = _job([loop_source, hyp_source])

    await job.run()

    hyp_source.send.assert_not_awaited()


async def test_no_candidates_sends_nothing():
    source = FakeSource("loop", [])
    job, _ = _job([source])
    await job.run()
    source.send.assert_not_awaited()


async def test_a_failing_source_does_not_block_the_others():
    broken = FakeSource("loop", [])
    broken.candidates = AsyncMock(side_effect=RuntimeError("store down"))
    hyp = make_hypothesis()
    hyp_source = FakeSource("hypothesis", [_hypothesis_candidate(hyp)])
    job, _ = _job([broken, hyp_source])

    with capture_logs() as logs:
        await job.run()

    hyp_source.send.assert_awaited_once()
    assert any(e["event"] == "attention_arbitration_source_failed" for e in logs)


async def test_job_id_is_attention_arbitration_sweep():
    job, _ = _job([])
    assert job.job_id == "attention_arbitration_sweep"


async def test_three_kinds_are_screened_and_sent_through_the_same_path():
    loop = make_loop(confidence=0.9)
    hyp = make_hypothesis(confidence=0.9, relevance=0.9)
    goal = make_stuck_goal()
    sources = [
        FakeSource("loop", [_loop_candidate(loop)], outcome="deduped"),
        FakeSource("goal", [_goal_candidate(goal)], outcome="deduped"),
        FakeSource("hypothesis", [_hypothesis_candidate(hyp)], outcome="deduped"),
    ]
    job, _ = _job(sources)

    await job.run()

    for source in sources:
        source.send.assert_awaited_once()
        (sent,) = source.send.await_args.args
        assert sent.source_kind == source.source_kind


# ── the bar holds through the job (SC-003) ───────────────────────────────────


async def test_bar_rejects_ungrounded_and_repeated_loop():
    ungrounded = make_loop(title="Ungrounded loop", confidence=0.9)
    repeated = make_loop(title="Repeated loop", confidence=0.9)
    ungrounded_c = _loop_candidate(ungrounded)
    repeated_c = _loop_candidate(repeated)
    embedder = FakeEmbedder({repeated_c.body: [1.0, 0.0], "pushed 3h ago": [1.0, 0.0]})
    bar = _bar(
        embedder=embedder,
        nli=FakeNLI({"Ungrounded loop": 0.0}),
        history=FakeHistory(["pushed 3h ago"]),
    )
    source = FakeSource("loop", [ungrounded_c, repeated_c])
    job, _ = _job([source], bar=bar)

    with capture_logs() as logs:
        await job.run()

    source.send.assert_not_awaited()
    rejected = {
        e["source_id"]: e["reason"] for e in logs if e["event"] == "push_bar_rejected"
    }
    assert rejected == {
        str(ungrounded.id): "ungrounded",
        str(repeated.id): "not_novel",
    }
    assert all(
        e["source_kind"] == "loop" for e in logs if e["event"] == "push_bar_rejected"
    )


async def test_loop_and_hypothesis_share_history():
    hyp = make_hypothesis(confidence=0.9, relevance=0.9)
    hyp_c = _hypothesis_candidate(hyp)
    # a loop push 3 hours ago is the body the hypothesis now repeats
    embedder = FakeEmbedder({hyp_c.body: [0.0, 1.0], "loop push": [0.0, 1.0]})
    bar = _bar(embedder=embedder, history=FakeHistory(["loop push"]))
    source = FakeSource("hypothesis", [hyp_c])
    job, _ = _job([source], bar=bar)

    with capture_logs() as logs:
        await job.run()

    source.send.assert_not_awaited()
    (rejection,) = [e for e in logs if e["event"] == "push_bar_rejected"]
    assert (rejection["source_kind"], rejection["reason"]) == (
        "hypothesis",
        "not_novel",
    )


async def test_inline_mention_blocks_push():
    loop = make_loop(confidence=0.9)
    source = FakeSource("loop", [_loop_candidate(loop)])
    job, _ = _job([source], bar=_bar(mentions=FakeMentions({loop.id})))

    with capture_logs() as logs:
        await job.run()

    source.send.assert_not_awaited()
    (rejection,) = [e for e in logs if e["event"] == "push_bar_rejected"]
    assert rejection["reason"] == "mentioned_recently"


async def test_dry_run_source_sends_nothing_and_logs():
    loop = make_loop(confidence=0.9)
    source = FakeSource("loop", [_loop_candidate(loop)], dry_run=True)
    job, _ = _job([source])

    with capture_logs() as logs:
        await job.run()

    source.send.assert_not_awaited()
    assert any(e["event"] == "push_candidate_dry_run" for e in logs)


async def test_cooling_candidate_is_never_screened():
    cooling = make_loop(title="Cooling", confidence=0.9)
    fresh = make_loop(title="Fresh", confidence=0.8)
    cooling_c, fresh_c = _loop_candidate(cooling), _loop_candidate(fresh)
    embedder = FakeEmbedder()
    nli = FakeNLI()
    source = FakeSource("loop", [cooling_c, fresh_c])
    notifier = _notifier(cooling={cooling_c.once_per.key})
    bar = _bar(embedder=embedder, nli=nli, history=FakeHistory(["x"]))
    job, _ = _job([source], bar=bar, notifier=notifier)

    with capture_logs() as logs:
        await job.run()

    (sent,) = source.send.await_args.args
    assert sent is fresh_c
    cooling_logs = [e for e in logs if e["event"] == "push_candidate_cooling"]
    assert [e["source_id"] for e in cooling_logs] == [str(cooling.id)]
    assert not any(e["event"] == "push_bar_rejected" for e in logs)
    assert cooling_c.body not in embedder.encoded


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
    a_c, b_c = _loop_candidate(a), _loop_candidate(b)
    source = FakeSource("loop", [a_c, b_c])
    view = _view(overrides=[_override(b, a, "above")], loop_store=loop_store)
    job, _ = _job([source], view=view)

    await job.run()

    source.send.assert_awaited_once_with(b_c)


async def test_an_item_the_user_pushed_down_is_never_sent_even_when_alone():
    a, b, loop_store = _active_loops()
    source = FakeSource("loop", [_loop_candidate(a)])
    view = _view(overrides=[_override(a, b, "below")], loop_store=loop_store)
    job, _ = _job([source], view=view)

    await job.run()

    source.send.assert_not_awaited()


async def test_a_pushed_down_item_does_not_block_the_next_candidate():
    a, b, loop_store = _active_loops()
    b_c = _loop_candidate(b)
    source = FakeSource("loop", [_loop_candidate(a), b_c])
    view = _view(overrides=[_override(a, b, "below")], loop_store=loop_store)
    job, _ = _job([source], view=view)

    await job.run()

    source.send.assert_awaited_once_with(b_c)


async def test_a_decayed_override_does_not_exclude_its_item():
    a, b, loop_store = _active_loops()
    a_c = _loop_candidate(a)
    source = FakeSource("loop", [a_c])
    view = _view(
        overrides=[_override(a, b, "below", pinned=False, age_hours=72)],
        loop_store=loop_store,
    )
    job, _ = _job([source], view=view)

    await job.run()

    source.send.assert_awaited_once_with(a_c)


# ── a drifting loop is pushed at most once per window (phase 204, US5) ───────


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def _stored_row(**kw) -> NotificationRow:
    values = dict(
        id="n-1",
        event_type="loop_drift",
        source="worldstate",
        title="T",
        body="B",
        target_type=None,
        target_id=None,
        target_parent_id=None,
        created_at=datetime(2026, 10, 26, tzinfo=UTC),
        read_at=None,
        push_class="discretionary",
        urgency="normal",
        format="text",
        actions=[],
        delivery="delivered",
        delivered_at=None,
    )
    values.update(kw)
    return NotificationRow(**values)


async def test_loop_repush_after_window():
    clock = Clock()
    loop = make_loop(confidence=0.9)
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[loop])
    loop_store.get = AsyncMock(return_value=loop)
    relevance = MagicMock()
    relevance.build = AsyncMock(return_value=object())
    relevance.score = MagicMock(return_value=MagicMock(value=0.9))

    store = AsyncMock()
    store.create = AsyncMock(side_effect=lambda **kw: _stored_row(**kw))
    interface = AsyncMock()
    # a roomy budget so only the 7-day claim decides
    notifier = ProactiveNotifier(
        interface,
        store,
        push_log=InMemoryPushLog(clock),
        max_discretionary_per_day=50,
        clock=clock,
    )
    surfacer = LoopSurfacer(
        loop_store=loop_store,
        graph_store=AsyncMock(),
        pool=None,
        relevance_model=relevance,
        notifier=notifier,
        settings=LoopPushSettings(repush_after_days=7.0),
    )
    # the bar passes everything: fake NLI grounds all, history is empty
    job = AttentionArbitrationJob(
        priority_view=_view(loop_store=loop_store),
        sources=[surfacer],
        bar=_bar(nli=None),
        notifier=notifier,
    )

    async def delivered() -> int:
        return len(
            [
                c
                for c in store.create.await_args_list
                if c.kwargs["delivery"] == "delivered"
            ]
        )

    await job.run()
    assert await delivered() == 1

    clock.now += timedelta(days=6)
    await job.run()
    assert await delivered() == 1

    clock.now += timedelta(days=2)
    await job.run()
    assert await delivered() == 2
