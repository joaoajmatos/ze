from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from ze_priority.scoring import score_hypothesis, score_loop, sort_and_rank

from tests.factories import make_hypothesis, make_loop

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
        make_hypothesis(id=large_id, confidence=0.5, relevance=1.0, created_at=same_time)
    )
    b = score_hypothesis(
        make_hypothesis(id=small_id, confidence=0.5, relevance=1.0, created_at=same_time)
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
