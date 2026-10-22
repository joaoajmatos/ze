from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze_agents.claims import ClaimKind, Confidence
from ze_priority.errors import ZePriorityError
from ze_priority.types import (
    PriorityCandidateRef,
    PriorityOverride,
    RelationshipSignal,
)
from ze_priority.view import PriorityView

from ze_worldstate.types import LoopState

from tests.factories import make_hypothesis, make_loop, make_stuck_goal

UTC = timezone.utc


def _view(
    loop_store=None,
    goal_store=None,
    hypothesis_store=None,
    relationship_source=None,
    override_store=None,
) -> PriorityView:
    return PriorityView(
        loop_store=loop_store or AsyncMock(),
        goal_store=goal_store or AsyncMock(),
        hypothesis_store=hypothesis_store or AsyncMock(),
        relationship_source=relationship_source,
        override_store=override_store,
    )


def _override(item_id, anchor_id, relation="above", *, pinned=True) -> PriorityOverride:
    return PriorityOverride(
        id=uuid4(),
        source_kind="loop",
        source_id=item_id,
        anchor_source_kind="loop",
        anchor_source_id=anchor_id,
        relation=relation,
        pinned=pinned,
        submitted_at=datetime.now(UTC),
        superseded_at=None,
        contribution_domain_id=uuid4(),
    )


def _two_loops():
    """A computes higher than B."""
    a = make_loop(title="A", confidence=0.9, state=LoopState.ACTIVE)
    b = make_loop(title="B", confidence=0.2, state=LoopState.ACTIVE)
    loop_store = AsyncMock()
    loop_store.list.return_value = [a, b]
    goal_store = AsyncMock()
    goal_store.list_stuck.return_value = []
    hypothesis_store = AsyncMock()
    hypothesis_store.list_recent.return_value = []
    return a, b, loop_store, goal_store, hypothesis_store


async def test_rank_combines_three_mocked_sources():
    loop = make_loop()
    stuck = make_stuck_goal()
    hyp = make_hypothesis()

    loop_store = AsyncMock()
    loop_store.list.return_value = [loop]
    goal_store = AsyncMock()
    goal_store.list_stuck.return_value = [stuck]
    hypothesis_store = AsyncMock()
    hypothesis_store.list_recent.return_value = [hyp]

    ranking = await _view(loop_store, goal_store, hypothesis_store).rank()

    assert len(ranking.items) == 3
    assert {item.source_kind for item in ranking.items} == {
        "loop",
        "goal",
        "hypothesis",
    }
    assert ranking.sources_succeeded == {"loop", "goal", "hypothesis"}
    assert ranking.sources_failed == set()

    by_kind = {item.source_kind: item for item in ranking.items}
    assert by_kind["loop"].source_id == loop.id
    assert by_kind["loop"].signal.confidence == loop.confidence
    assert by_kind["goal"].source_id == stuck.goal.id
    assert by_kind["goal"].signal.idle_days == stuck.idle_days
    assert by_kind["hypothesis"].source_id == hyp.id
    assert by_kind["hypothesis"].signal.confidence == hyp.confidence
    assert by_kind["hypothesis"].signal.relevance == hyp.relevance


async def test_long_drifting_loop_outranks_fresh_low_confidence_hypothesis():
    loop = make_loop(confidence=0.5, updated_at=datetime.now(UTC) - timedelta(days=10))
    hyp = make_hypothesis(
        confidence=0.2, relevance=0.3, created_at=datetime.now(UTC) - timedelta(hours=1)
    )

    loop_store = AsyncMock()
    loop_store.list.return_value = [loop]
    goal_store = AsyncMock()
    goal_store.list_stuck.return_value = []
    hypothesis_store = AsyncMock()
    hypothesis_store.list_recent.return_value = [hyp]

    ranking = await _view(loop_store, goal_store, hypothesis_store).rank()

    assert ranking.items[0].source_kind == "loop"
    assert ranking.items[0].rank == 1


async def test_single_source_failure_degrades_gracefully():
    loop = make_loop()
    stuck = make_stuck_goal()

    loop_store = AsyncMock()
    loop_store.list.return_value = [loop]
    goal_store = AsyncMock()
    goal_store.list_stuck.return_value = [stuck]
    hypothesis_store = AsyncMock()
    hypothesis_store.list_recent.side_effect = RuntimeError("db unreachable")

    ranking = await _view(loop_store, goal_store, hypothesis_store).rank()

    assert ranking.sources_failed == {"hypothesis"}
    assert ranking.sources_succeeded == {"loop", "goal"}
    assert {item.source_kind for item in ranking.items} == {"loop", "goal"}


async def test_all_sources_failing_raises():
    loop_store = AsyncMock()
    loop_store.list.side_effect = RuntimeError("db down")
    goal_store = AsyncMock()
    goal_store.list_stuck.side_effect = RuntimeError("db down")
    hypothesis_store = AsyncMock()
    hypothesis_store.list_recent.side_effect = RuntimeError("db down")

    with pytest.raises(ZePriorityError):
        await _view(loop_store, goal_store, hypothesis_store).rank()


# ── relationship-staleness source (US3) ────────────────────────────────────────


async def test_rank_includes_relationship_source_when_configured():
    loop = make_loop()
    stuck = make_stuck_goal()
    hyp = make_hypothesis()

    loop_store = AsyncMock()
    loop_store.list.return_value = [loop]
    goal_store = AsyncMock()
    goal_store.list_stuck.return_value = [stuck]
    hypothesis_store = AsyncMock()
    hypothesis_store.list_recent.return_value = [hyp]
    relationship_source = AsyncMock()
    relationship_source.list_stale_for_follow_up.return_value = [
        RelationshipSignal(name="Alice", days_ago=60)
    ]

    ranking = await _view(
        loop_store, goal_store, hypothesis_store, relationship_source
    ).rank()

    assert {item.source_kind for item in ranking.items} == {
        "loop",
        "goal",
        "hypothesis",
        "relationship",
    }
    assert ranking.sources_succeeded == {"loop", "goal", "hypothesis", "relationship"}
    by_kind = {item.source_kind: item for item in ranking.items}
    assert by_kind["relationship"].title == "Alice"
    assert by_kind["relationship"].signal.days_ago == 60


async def test_rank_can_surface_relationship_item_as_highest_ranked():
    from ze_worldstate.types import LoopState

    loop = make_loop(confidence=0.1, state=LoopState.ACTIVE)
    loop_store = AsyncMock()
    loop_store.list.return_value = [loop]
    goal_store = AsyncMock()
    goal_store.list_stuck.return_value = []
    hypothesis_store = AsyncMock()
    hypothesis_store.list_recent.return_value = []
    relationship_source = AsyncMock()
    relationship_source.list_stale_for_follow_up.return_value = [
        RelationshipSignal(name="Alice", days_ago=200)
    ]

    ranking = await _view(
        loop_store, goal_store, hypothesis_store, relationship_source
    ).rank()

    assert ranking.items[0].source_kind == "relationship"
    assert ranking.items[0].rank == 1


async def test_relationship_source_failure_degrades_gracefully_fr010():
    loop = make_loop()
    loop_store = AsyncMock()
    loop_store.list.return_value = [loop]
    goal_store = AsyncMock()
    goal_store.list_stuck.return_value = []
    hypothesis_store = AsyncMock()
    hypothesis_store.list_recent.return_value = []
    relationship_source = AsyncMock()
    relationship_source.list_stale_for_follow_up.side_effect = RuntimeError(
        "db unreachable"
    )

    ranking = await _view(
        loop_store, goal_store, hypothesis_store, relationship_source
    ).rank()

    assert ranking.sources_failed == {"relationship"}
    assert "relationship" not in ranking.sources_succeeded
    assert {item.source_kind for item in ranking.items} == {"loop"}


async def test_relationship_source_none_is_skipped_not_counted_as_failed():
    loop = make_loop()
    loop_store = AsyncMock()
    loop_store.list.return_value = [loop]
    goal_store = AsyncMock()
    goal_store.list_stuck.return_value = []
    hypothesis_store = AsyncMock()
    hypothesis_store.list_recent.return_value = []

    ranking = await _view(loop_store, goal_store, hypothesis_store, None).rank()

    assert "relationship" not in ranking.sources_failed
    assert "relationship" not in ranking.sources_succeeded


async def test_priority_view_without_relationship_source_still_works():
    """Regression: the existing three-store constructor signature keeps working
    unchanged when relationship_source is omitted entirely."""
    loop = make_loop()
    loop_store = AsyncMock()
    loop_store.list.return_value = [loop]
    goal_store = AsyncMock()
    goal_store.list_stuck.return_value = []
    hypothesis_store = AsyncMock()
    hypothesis_store.list_recent.return_value = []

    view = PriorityView(
        loop_store=loop_store,
        goal_store=goal_store,
        hypothesis_store=hypothesis_store,
    )
    ranking = await view.rank()

    assert {item.source_kind for item in ranking.items} == {"loop"}


async def test_rank_subset_places_candidates_by_the_full_ranking():
    a, b, loop_store, goal_store, hypothesis_store = _two_loops()
    override_store = AsyncMock()
    override_store.get_active.return_value = [_override(b.id, a.id)]
    hyp = make_hypothesis()

    ranking = await _view(
        loop_store, goal_store, hypothesis_store, override_store=override_store
    ).rank_subset(
        [
            PriorityCandidateRef(source_kind="loop", entity=a),
            PriorityCandidateRef(source_kind="loop", entity=b),
            PriorityCandidateRef(source_kind="hypothesis", entity=hyp),
        ]
    )

    assert [item.source_id for item in ranking.items] == [b.id, a.id, hyp.id]


async def test_rank_subset_scores_candidates_when_every_source_fails():
    loop = make_loop()
    hyp = make_hypothesis()
    failing = AsyncMock()
    failing.list.side_effect = RuntimeError("db down")
    failing.list_stuck.side_effect = RuntimeError("db down")
    failing.list_recent.side_effect = RuntimeError("db down")

    ranking = await _view(failing, failing, failing).rank_subset(
        [
            PriorityCandidateRef(source_kind="loop", entity=loop),
            PriorityCandidateRef(source_kind="hypothesis", entity=hyp),
        ]
    )

    assert {item.source_id for item in ranking.items} == {loop.id, hyp.id}


async def test_priority_item_round_trips_as_a_priority_claim_shape():
    """FR-004: PriorityItem must be expressible as a Priority-kind claim —
    a ClaimKind + Confidence, with no missing fields."""
    stuck = make_stuck_goal()
    goal_store = AsyncMock()
    goal_store.list_stuck.return_value = [stuck]
    loop_store = AsyncMock()
    loop_store.list.return_value = []
    hypothesis_store = AsyncMock()
    hypothesis_store.list_recent.return_value = []

    ranking = await _view(loop_store, goal_store, hypothesis_store).rank()

    item = ranking.items[0]
    assert item.claim_kind == ClaimKind.PRIORITY
    assert isinstance(item.priority, Confidence)
    assert 0.0 <= item.priority.value <= 1.0
    assert item.source_id is not None
    assert item.title
    assert item.rank == 1
    assert item.activity_at is not None


async def test_rank_reads_hypotheses_through_list_recent():
    """list_recent carries the dismissed-feedback predicate (pinned in ze-correlation)."""
    hypothesis_store = AsyncMock()
    hypothesis_store.list_recent.return_value = []

    await _view(
        AsyncMock(list=AsyncMock(return_value=[])), None, hypothesis_store
    ).rank()

    hypothesis_store.list_recent.assert_awaited_once()


# ── the user's order (phase 198, B5) ───────────────────────────────────────────


async def test_rank_returns_the_users_order_with_the_computed_rank_kept():
    a, b, loop_store, goal_store, hypothesis_store = _two_loops()
    override_store = AsyncMock()
    override_store.get_active.return_value = [_override(b.id, a.id)]

    ranking = await _view(
        loop_store, goal_store, hypothesis_store, override_store=override_store
    ).rank()

    assert [item.source_id for item in ranking.items] == [b.id, a.id]
    top, second = ranking.items
    assert (top.rank, top.computed_rank) == (1, 2)
    assert top.override is not None and top.override.source_id == b.id
    assert (second.rank, second.computed_rank) == (2, 1)
    assert second.override is None


async def test_rank_without_overrides_keeps_the_computed_order():
    a, b, loop_store, goal_store, hypothesis_store = _two_loops()
    override_store = AsyncMock()
    override_store.get_active.return_value = []

    ranking = await _view(
        loop_store, goal_store, hypothesis_store, override_store=override_store
    ).rank()

    assert [item.source_id for item in ranking.items] == [a.id, b.id]
    assert [(i.rank, i.computed_rank) for i in ranking.items] == [(1, 1), (2, 2)]


async def test_override_store_failure_returns_the_computed_order_and_warns(
    monkeypatch,
):
    log = MagicMock()
    monkeypatch.setattr("ze_priority.view.log", log)
    a, b, loop_store, goal_store, hypothesis_store = _two_loops()
    override_store = AsyncMock()
    override_store.get_active.side_effect = RuntimeError("db unreachable")

    ranking = await _view(
        loop_store, goal_store, hypothesis_store, override_store=override_store
    ).rank()

    assert [item.source_id for item in ranking.items] == [a.id, b.id]
    events = [c.args[0] for c in log.warning.call_args_list]
    assert events == ["priority_overrides_unavailable"]


async def test_override_store_is_not_read_when_there_are_no_items():
    loop_store = AsyncMock()
    loop_store.list.return_value = []
    goal_store = AsyncMock()
    goal_store.list_stuck.return_value = []
    hypothesis_store = AsyncMock()
    hypothesis_store.list_recent.return_value = []
    override_store = AsyncMock()

    ranking = await _view(
        loop_store, goal_store, hypothesis_store, override_store=override_store
    ).rank()

    assert ranking.items == []
    override_store.get_active.assert_not_awaited()
