from __future__ import annotations

from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze_priority.errors import ZePriorityError
from ze_priority.scoring import score_goal, score_hypothesis, score_loop, sort_and_rank
from ze_priority.turn import (
    INLINE_MENTION_LIMIT,
    OFFER_COOLDOWN_HOURS,
    OFFER_LIMIT,
    TurnSurfacing,
)
from ze_priority.types import LoopOffer, PriorityOverride, PriorityRanking
from ze_priority.view import PriorityView

from ze_worldstate.types import LoopState

from tests.factories import make_hypothesis, make_loop, make_stuck_goal

UTC = timezone.utc


def _surfacer(
    view, override_store=None, graph_store=None, loop_store=None, push_log=None
):
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
    stuck = score_goal(
        make_stuck_goal(goal_overrides={"title": "Stuck goal"}, idle_days=1)
    )
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
    loop_store.get = AsyncMock(
        return_value=make_loop(id=loop.source_id, title=loop.title)
    )

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

    mentions = await _surfacer(_view(ranking), graph_store=graph_store).inline_mentions(
        [entity_id], entities=[entity]
    )

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


# ── Phase 171: recap cap ─────────────────────────────────────────────────────


async def test_recap_mentions_limit_slices_the_merged_order():
    loops = [
        score_loop(make_loop(title=f"Loop {i}", confidence=0.9 - i * 0.05))
        for i in range(8)
    ]
    ranking = _ranking(*loops)
    surfacer = _surfacer(_view(ranking))

    everything = await surfacer.recap_mentions()
    capped = await surfacer.recap_mentions(limit=5)

    assert len(everything) == 8
    assert [m.title for m in capped] == [m.title for m in everything[:5]]


async def test_recap_mentions_limit_keeps_pinned_item_first():
    loops = [score_loop(make_loop(title=f"Loop {i}")) for i in range(6)]
    stuck = score_goal(make_stuck_goal(goal_overrides={"title": "Pinned"}, idle_days=1))
    ranking = _ranking(*loops, stuck)
    first = ranking.items[0]
    store = AsyncMock()
    store.get_active = AsyncMock(return_value=[_override(stuck, first)])

    capped = await _surfacer(_view(ranking), store).recap_mentions(limit=5)

    assert len(capped) == 5
    assert capped[0].title == "Pinned"


# ── Phase 171: resume loop offers ────────────────────────────────────────────


def _suspected(title, *, confidence=0.35, created_days_ago=1, **kw):
    created = (
        None
        if created_days_ago is None
        else datetime.now(UTC) - timedelta(days=created_days_ago)
    )
    return make_loop(
        title=title,
        state=LoopState.SUSPECTED,
        confidence=confidence,
        created_at=created,
        provenance=kw.pop("provenance", "email"),
        **kw,
    )


class _PushLog:
    """Fake push_log storing (event_type, sent_at) against an injectable clock."""

    def __init__(self) -> None:
        self.now = datetime(2026, 10, 1, tzinfo=UTC)
        self.rows: list[tuple[str, datetime]] = []

    async def was_sent_within_hours(self, event_type, hours):
        cutoff = self.now - timedelta(hours=hours)
        return any(e == event_type and at > cutoff for e, at in self.rows)

    async def log(self, event_type, payload=None):
        self.rows.append((event_type, self.now))


def _offer_surfacer(loops, push_log):
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=loops)
    return _surfacer(_view(), loop_store=loop_store, push_log=push_log), loop_store


async def test_offers_pick_three_ordered_by_confidence_then_recency():
    loops = [
        _suspected("low old", confidence=0.3, created_days_ago=9),
        _suspected("top", confidence=0.5, created_days_ago=5),
        _suspected("mid newer", confidence=0.4, created_days_ago=1),
        _suspected("mid older", confidence=0.4, created_days_ago=6),
        _suspected("low new", confidence=0.3, created_days_ago=2),
    ]
    push_log = _PushLog()
    surfacer, loop_store = _offer_surfacer(loops, push_log)

    offers = await surfacer.resume_loop_offers()

    assert [o.title for o in offers] == ["top", "mid newer", "mid older"]
    assert len(offers) == OFFER_LIMIT
    assert all(isinstance(o, LoopOffer) for o in offers)
    loop_store.list.assert_awaited_once_with(states=["suspected"])
    assert sorted(e for e, _ in push_log.rows) == sorted(
        f"worldstate_loop_offer:{o.loop_id}" for o in offers
    )


async def test_offers_sort_missing_created_at_last():
    loops = [
        _suspected("undated", created_days_ago=None),
        _suspected("dated", created_days_ago=3),
    ]
    surfacer, _ = _offer_surfacer(loops, _PushLog())

    offers = await surfacer.resume_loop_offers()

    assert [o.title for o in offers] == ["dated", "undated"]


async def test_offer_cooldown_skips_and_next_fills_the_slot():
    loops = [_suspected(f"L{i}", confidence=0.5 - i * 0.05) for i in range(4)]
    push_log = _PushLog()
    push_log.rows.append((f"worldstate_loop_offer:{loops[0].id}", push_log.now))
    surfacer, _ = _offer_surfacer(loops, push_log)

    offers = await surfacer.resume_loop_offers()

    assert [o.title for o in offers] == ["L1", "L2", "L3"]


async def test_offers_empty_without_push_log():
    surfacer, _ = _offer_surfacer([_suspected("x")], None)
    assert await surfacer.resume_loop_offers() == []


async def test_offers_empty_when_list_raises():
    surfacer, loop_store = _offer_surfacer([], _PushLog())
    loop_store.list = AsyncMock(side_effect=RuntimeError("db"))
    assert await surfacer.resume_loop_offers() == []


async def test_offers_empty_and_nothing_logged_when_cooldown_check_raises():
    push_log = _PushLog()
    push_log.was_sent_within_hours = AsyncMock(side_effect=RuntimeError("db"))
    surfacer, _ = _offer_surfacer([_suspected("x")], push_log)

    assert await surfacer.resume_loop_offers() == []
    assert push_log.rows == []


async def test_offers_survive_a_failing_log_write():
    push_log = _PushLog()
    push_log.log = AsyncMock(side_effect=RuntimeError("db"))
    surfacer, _ = _offer_surfacer([_suspected("x")], push_log)

    offers = await surfacer.resume_loop_offers()

    assert [o.title for o in offers] == ["x"]


async def test_offers_never_repeat_inside_cooldown_over_two_weeks():
    loops = [_suspected(f"L{i}", confidence=0.5 - i * 0.05) for i in range(4)]
    push_log = _PushLog()
    surfacer, _ = _offer_surfacer(loops, push_log)
    offered_on: dict = {loop.id: [] for loop in loops}

    for _day in range(14):
        for offer in await surfacer.resume_loop_offers():
            offered_on[offer.loop_id].append(push_log.now)
        push_log.now += timedelta(hours=24)

    cooldown = timedelta(hours=OFFER_COOLDOWN_HOURS)
    for times in offered_on.values():
        assert len(times) <= 2
        assert all(b - a >= cooldown for a, b in zip(times, times[1:]))
