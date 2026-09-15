from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from ze_priority.scoring import (
    score_goal,
    score_hypothesis,
    score_loop,
    score_relationship_staleness,
    sort_and_rank,
)
from ze_priority.types import RelationshipSignal

from tests.factories import make_hypothesis, make_loop, make_stuck_goal

UTC = timezone.utc


def test_tie_break_by_activity_at_then_source_id():
    now = datetime.now(UTC)

    older_id = UUID(int=1)
    newer_id = UUID(int=2)

    older = score_loop(
        make_loop(id=older_id, confidence=0.5, updated_at=now - timedelta(days=2)),
        now=now,
    )
    newer = score_loop(
        make_loop(id=newer_id, confidence=0.5, updated_at=now - timedelta(days=1)),
        now=now,
    )
    # Force equal priority values so the tie-break path is exercised.
    older.priority.value = 0.5
    newer.priority.value = 0.5

    ranked = sort_and_rank([older, newer])

    assert [item.source_id for item in ranked] == [newer_id, older_id]
    assert ranked[0].rank == 1
    assert ranked[1].rank == 2


def test_tie_break_falls_back_to_source_id_ascending():
    now = datetime.now(UTC)
    same_time = now - timedelta(days=1)

    small_id = UUID(int=1)
    large_id = UUID(int=2)

    a = score_hypothesis(
        make_hypothesis(
            id=large_id, confidence=0.5, relevance=1.0, created_at=same_time
        )
    )
    b = score_hypothesis(
        make_hypothesis(
            id=small_id, confidence=0.5, relevance=1.0, created_at=same_time
        )
    )

    ranked = sort_and_rank([a, b])

    assert [item.source_id for item in ranked] == [small_id, large_id]


def test_rank_is_contiguous_one_indexed():
    items = [
        score_hypothesis(make_hypothesis(confidence=v, relevance=1.0))
        for v in (0.9, 0.1, 0.5)
    ]
    ranked = sort_and_rank(items)
    assert [item.rank for item in ranked] == [1, 2, 3]
    assert [round(item.priority.value, 2) for item in ranked] == [0.9, 0.5, 0.1]


def test_score_hypothesis_copies_entities_and_hedges_unconfirmed():
    entity_id = UUID(int=7)
    item = score_hypothesis(
        make_hypothesis(entities=[entity_id], confirmed=False, summary="maybe linked")
    )
    assert item.linked_entity_ids == (entity_id,)
    assert item.hedge is True


def test_score_hypothesis_does_not_hedge_confirmed():
    item = score_hypothesis(make_hypothesis(confirmed=True))
    assert item.hedge is False


def test_score_goal_match_text_includes_title_and_objective():
    stuck = make_stuck_goal(
        goal_overrides={"title": "Ship the contract", "objective": "Send Maria the PDF"}
    )
    item = score_goal(stuck)
    assert "Ship the contract" in item.match_text
    assert "Send Maria the PDF" in item.match_text


def test_score_relationship_match_text_is_name():
    item = score_relationship_staleness(RelationshipSignal(name="Maria Silva", days_ago=14))
    assert item.match_text == "Maria Silva"


def test_score_loop_carries_drift_rationale():
    loop = make_loop(drift_rationale="No update since Tuesday.")
    item = score_loop(loop)
    assert item.signal.drift_rationale == "No update since Tuesday."
