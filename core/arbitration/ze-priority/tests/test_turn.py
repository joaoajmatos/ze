from __future__ import annotations

from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze_priority.errors import ZePriorityError
from ze_priority.scoring import score_goal, score_hypothesis, score_loop, sort_and_rank
from ze_priority.turn import INLINE_MENTION_LIMIT, TurnSurfacing
from ze_priority.types import PriorityOverride, PriorityRanking
from ze_priority.view import PriorityView

from tests.factories import make_hypothesis, make_loop, make_stuck_goal

UTC = timezone.utc


def _surfacer(view, override_store=None, graph_store=None, loop_store=None, push_log=None):
    return TurnSurfacing(
        priority_view=view,
        override_store=override_store,
        graph_store=graph_store or AsyncMock(),
        loop_store=loop_store or AsyncMock(),
        push_log=push_log,
    )


def _override(item, anchor, *, pinned=True):
    return PriorityOverride(
        id=uuid4(),
        source_kind=item.source_kind,
        source_id=item.source_id,
        anchor_source_kind=anchor.source_kind,
        anchor_source_id=anchor.source_id,
        relation="above",
        pinned=pinned,
        submitted_at=datetime.now(UTC),
        superseded_at=None,
        contribution_domain_id=uuid4(),
    )


def _entity(entity_id, name):
    return SimpleNamespace(id=entity_id, canonical_name=name, aliases=[])


def _ranking(*source_items):
    return PriorityRanking(
        items=sort_and_rank(list(source_items)),
        sources_succeeded={"loop", "goal", "hypothesis"},
        sources_failed=set(),
        generated_at=datetime.now(UTC),
    )


def _view(ranking=None, error=None):
    view = MagicMock(spec=PriorityView)
    if error is not None:
        view.rank = AsyncMock(side_effect=error)
    else:
        view.rank = AsyncMock(return_value=ranking)
    return view


async def test_recap_follows_pinned_goal_above_loop():
    loop = score_loop(make_loop(title="Drifting loop", confidence=0.9))
    stuck = score_goal(make_stuck_goal(goal_overrides={"title": "Stuck goal"}, idle_days=1))
    ranking = _ranking(loop, stuck)
    store = AsyncMock()
    store.get_active = AsyncMock(return_value=[_override(stuck, loop)])

    mentions = await _surfacer(_view(ranking), store).recap_mentions()

    assert [m.title for m in mentions] == ["Stuck goal", "Drifting loop"]
    assert mentions[0].source_kind == "goal"


async def test_recap_empty_when_all_sources_fail():
    mentions = await _surfacer(
        _view(error=ZePriorityError("all PriorityView sources failed"))
    ).recap_mentions()
    assert mentions == []


async def test_override_store_failure_still_returns_unmerged_rank():
    loop = score_loop(make_loop(title="Loop", confidence=0.95))
    stuck = score_goal(make_stuck_goal(goal_overrides={"title": "Goal"}, idle_days=1))
    ranking = _ranking(loop, stuck)
    store = AsyncMock()
    store.get_active = AsyncMock(side_effect=RuntimeError("db down"))

    mentions = await _surfacer(_view(ranking), store).recap_mentions()

    assert [m.title for m in mentions] == ["Loop", "Goal"]


async def test_inline_mentions_goal_beats_overlapping_loop_when_pinned():
    entity_id = uuid4()
    loop = score_loop(make_loop(title="Loop about Maria"))
    stuck = score_goal(
        make_stuck_goal(
            goal_overrides={
                "title": "Send Maria the contract",
                "objective": "Maria gets the PDF",
            }
        )
    )
    ranking = _ranking(loop, stuck)
    store = AsyncMock()
    store.get_active = AsyncMock(return_value=[_override(stuck, loop)])

    graph_store = AsyncMock()
    graph_store.list_relationships = AsyncMock(
        return_value=[
            MagicMock(target_id=loop.source_id, target_type="open_loop"),
        ]
    )
    loop_store = AsyncMock()
    loop_store.get = AsyncMock(return_value=make_loop(id=loop.source_id, title=loop.title))

    entity = _entity(entity_id, "Maria")
    mentions = await _surfacer(
        _view(ranking), store, graph_store=graph_store, loop_store=loop_store
    ).inline_mentions([entity_id], entities=[entity])

    assert mentions[0].title == "Send Maria the contract"
    assert mentions[0].source_kind == "goal"


async def test_inline_mentions_skips_unrelated_global_top():
    entity_id = uuid4()
    other = score_loop(make_loop(title="Unrelated top loop", confidence=0.99))
    ranking = _ranking(other)
    graph_store = AsyncMock()
    graph_store.list_relationships = AsyncMock(return_value=[])
    entity = _entity(entity_id, "Passport")

    mentions = await _surfacer(
        _view(ranking), graph_store=graph_store
    ).inline_mentions([entity_id], entities=[entity])

    assert mentions == []


async def test_inline_mentions_empty_without_overlap():
    mentions = await _surfacer(_view(_ranking())).inline_mentions([])
    assert mentions == []


async def test_inline_mentions_caps_at_three():
    entity_id = uuid4()
    entity = _entity(entity_id, "Maria")
    items = [
        score_goal(
            make_stuck_goal(
                goal_overrides={"title": f"Maria task {i}", "objective": "Maria"},
                idle_days=i,
            )
        )
        for i in range(5)
    ]
    ranking = _ranking(*items)

    mentions = await _surfacer(_view(ranking)).inline_mentions(
        [entity_id], entities=[entity]
    )
    assert len(mentions) == INLINE_MENTION_LIMIT


async def test_unconfirmed_hypothesis_mention_is_hedged():
    entity_id = uuid4()
    hyp = score_hypothesis(
        make_hypothesis(
            summary="Maria may be on Launch",
            entities=[entity_id],
            confirmed=False,
        )
    )
    ranking = _ranking(hyp)
    entity = _entity(entity_id, "Maria")

    mentions = await _surfacer(_view(ranking)).inline_mentions(
        [entity_id], entities=[entity]
    )

    assert mentions
    assert "may still be open" in mentions[0].mention_text


async def test_inline_mentions_empty_on_total_rank_failure():
    entity_id = uuid4()
    mentions = await _surfacer(
        _view(error=ZePriorityError("all failed"))
    ).inline_mentions(
        [entity_id],
        entities=[_entity(entity_id, "X")],
    )
    assert mentions == []


async def test_loop_inline_writes_push_log_key():
    entity_id = uuid4()
    loop = score_loop(make_loop(title="Follow up with Maria"))
    ranking = _ranking(loop)
    graph_store = AsyncMock()
    graph_store.list_relationships = AsyncMock(
        return_value=[MagicMock(target_id=loop.source_id, target_type="open_loop")]
    )
    loop_store = AsyncMock()
    loop_store.get = AsyncMock(return_value=make_loop(id=loop.source_id))
    push_log = AsyncMock()

    await _surfacer(
        _view(ranking),
        graph_store=graph_store,
        loop_store=loop_store,
        push_log=push_log,
    ).inline_mentions(
        [entity_id],
        entities=[_entity(entity_id, "Maria")],
    )

    push_log.log.assert_awaited_once_with(f"worldstate_loop_inline:{loop.source_id}")


@pytest.mark.parametrize(
    "prompt",
    [
        "what's open right now",
        "What is open?",
        "whats outstanding",
        "What's on my plate",
    ],
)
def test_is_global_open_query_positive(prompt):
    assert TurnSurfacing.is_global_open_query(prompt) is True


@pytest.mark.parametrize(
    "prompt",
    ["how's the weather", "open the door", "tell me a joke", ""],
)
def test_is_global_open_query_negative(prompt):
    assert TurnSurfacing.is_global_open_query(prompt) is False
