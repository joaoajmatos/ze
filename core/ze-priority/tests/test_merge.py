from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from ze_agents.claims import ClaimKind, Confidence, DecayProfile

from ze_priority.merge import merge
from ze_priority.types import PriorityItem, PriorityOverride, PriorityRanking

UTC = timezone.utc


def _item(rank: int, *, source_kind: str = "loop") -> PriorityItem:
    return PriorityItem(
        source_kind=source_kind,
        claim_kind=ClaimKind.PRIORITY,
        source_id=uuid4(),
        title=f"item-{rank}",
        signal=None,
        priority=Confidence(
            value=1.0 - rank * 0.1, decay_profile=DecayProfile.TIME_LINEAR
        ),
        rank=rank,
        activity_at=datetime.now(UTC),
    )


def _ranking(items: list[PriorityItem]) -> PriorityRanking:
    return PriorityRanking(
        items=items,
        sources_succeeded={"loop", "goal", "hypothesis"},
        sources_failed=set(),
        generated_at=datetime.now(UTC),
    )


def _override(
    item: PriorityItem,
    anchor: PriorityItem,
    relation,
    *,
    pinned=False,
    submitted_at=None,
) -> PriorityOverride:
    return PriorityOverride(
        id=uuid4(),
        source_kind=item.source_kind,
        source_id=item.source_id,
        anchor_source_kind=anchor.source_kind,
        anchor_source_id=anchor.source_id,
        relation=relation,
        pinned=pinned,
        submitted_at=submitted_at or datetime.now(UTC),
        superseded_at=None,
        contribution_domain_id=uuid4(),
    )


def test_no_active_overrides_is_pass_through():
    items = [_item(1), _item(2), _item(3)]
    ranking = _ranking(items)

    merged = merge(ranking, [], datetime.now(UTC))

    assert [m.source_id for m in merged] == [i.source_id for i in items]
    assert all(not m.overridden_from_computed for m in merged)
    assert all(m.displayed_rank == m.computed_rank for m in merged)


def test_full_weight_override_repositions_adjacent_to_anchor():
    a, b, c = _item(1), _item(2), _item(3)
    ranking = _ranking([a, b, c])
    override = _override(c, a, "above", submitted_at=datetime.now(UTC))

    merged = merge(ranking, [override], datetime.now(UTC))

    order = [m.source_id for m in merged]
    assert order == [c.source_id, a.source_id, b.source_id]
    moved = next(m for m in merged if m.source_id == c.source_id)
    assert moved.overridden_from_computed is True
    assert moved.computed_rank == 3  # underlying score untouched


def test_weight_interpolated_at_24h_into_48h_window():
    a, b, c = _item(1), _item(2), _item(3)
    ranking = _ranking([a, b, c])
    submitted_at = datetime.now(UTC) - timedelta(hours=24)
    override = _override(c, a, "above", submitted_at=submitted_at)

    merged = merge(ranking, [override], datetime.now(UTC))

    # weight ~0.5: blended index = round(2 + 0.5*(0-2)) = round(1) = 1 -> between a and c's original slot
    order = [m.source_id for m in merged]
    assert order[1] == c.source_id


def test_weight_zero_at_48h_reverts_to_unmodified_position():
    a, b, c = _item(1), _item(2), _item(3)
    ranking = _ranking([a, b, c])
    submitted_at = datetime.now(UTC) - timedelta(hours=48)
    override = _override(c, a, "above", submitted_at=submitted_at)

    merged = merge(ranking, [override], datetime.now(UTC))

    order = [m.source_id for m in merged]
    assert order == [a.source_id, b.source_id, c.source_id]


def test_pinned_override_holds_full_weight_regardless_of_elapsed_time():
    a, b, c = _item(1), _item(2), _item(3)
    ranking = _ranking([a, b, c])
    submitted_at = datetime.now(UTC) - timedelta(days=30)
    override = _override(c, a, "above", pinned=True, submitted_at=submitted_at)

    merged = merge(ranking, [override], datetime.now(UTC))

    order = [m.source_id for m in merged]
    assert order == [c.source_id, a.source_id, b.source_id]


def test_stale_target_excluded_from_merge():
    a, b = _item(1), _item(2)
    stale = _item(3)
    ranking = _ranking([a, b])  # stale item no longer present
    override = _override(stale, a, "above")

    merged = merge(ranking, [override], datetime.now(UTC))

    assert [m.source_id for m in merged] == [a.source_id, b.source_id]


def test_contradicting_overrides_resolve_most_recent_submitted_at_wins():
    a, b, c = _item(1), _item(2), _item(3)
    ranking = _ranking([a, b, c])
    now = datetime.now(UTC)
    # Contradictory requests about the relative order of a and c — later wins (R7).
    earlier = _override(a, c, "above", submitted_at=now - timedelta(minutes=2))
    later = _override(c, a, "above", submitted_at=now - timedelta(minutes=1))

    merged = merge(ranking, [earlier, later], now)

    order = [m.source_id for m in merged]
    assert order.index(c.source_id) < order.index(a.source_id)
