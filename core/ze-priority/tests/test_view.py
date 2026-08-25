from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from ze_agents.claims import ClaimKind, Confidence
from ze_priority.errors import ZePriorityError
from ze_priority.types import PriorityCandidateRef
from ze_priority.view import PriorityView

from tests.factories import make_hypothesis, make_loop, make_stuck_goal

UTC = timezone.utc


def _view(loop_store=None, goal_store=None, hypothesis_store=None) -> PriorityView:
    return PriorityView(
        loop_store=loop_store or AsyncMock(),
        goal_store=goal_store or AsyncMock(),
        hypothesis_store=hypothesis_store or AsyncMock(),
    )


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
    assert {item.source_kind for item in ranking.items} == {"loop", "goal", "hypothesis"}
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
    hyp = make_hypothesis(confidence=0.2, relevance=0.3, created_at=datetime.now(UTC) - timedelta(hours=1))

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


async def test_rank_subset_never_touches_the_stores():
    loop = make_loop()
    hyp = make_hypothesis()

    loop_store = AsyncMock()
    goal_store = AsyncMock()
    hypothesis_store = AsyncMock()

    ranking = await _view(loop_store, goal_store, hypothesis_store).rank_subset(
        [
            PriorityCandidateRef(source_kind="loop", entity=loop),
            PriorityCandidateRef(source_kind="hypothesis", entity=hyp),
        ]
    )

    loop_store.list.assert_not_called()
    goal_store.list_stuck.assert_not_called()
    hypothesis_store.list_recent.assert_not_called()
    assert len(ranking.items) == 2


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
