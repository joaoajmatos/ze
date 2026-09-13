from __future__ import annotations

from datetime import datetime, timezone

from ze_priority.types import MergedPriorityItem, PriorityOverride, PriorityRanking

UTC = timezone.utc

_DECAY_WINDOW_HOURS = 48.0


def _decay_weight(override: PriorityOverride, now: datetime) -> float:
    if override.pinned:
        return 1.0
    elapsed_hours = (now - override.submitted_at).total_seconds() / 3600.0
    if elapsed_hours <= 0:
        return 1.0
    if elapsed_hours >= _DECAY_WINDOW_HOURS:
        return 0.0
    return 1.0 - (elapsed_hours / _DECAY_WINDOW_HOURS)


def merge(
    ranking: PriorityRanking,
    overrides: list[PriorityOverride],
    now: datetime,
) -> list[MergedPriorityItem]:
    """Combine `ranking`'s unmodified order with active `overrides` (data-model.md
    "Ranking merge"). Pure function — no persistence, no I/O."""
    items_by_id = {item.source_id: item for item in ranking.items}
    order: list = [item.source_id for item in ranking.items]

    active = sorted(
        (o for o in overrides if o.superseded_at is None),
        key=lambda o: o.submitted_at,
    )

    applied_override_by_item: dict = {}

    for override in active:
        if override.source_id not in items_by_id:
            continue  # FR-011 — stale target, no longer in PriorityView
        if override.anchor_source_id not in items_by_id:
            continue  # FR-011 — stale anchor
        weight = _decay_weight(override, now)
        if weight <= 0:
            continue

        current_index = order.index(override.source_id)
        order.remove(override.source_id)
        anchor_index = order.index(override.anchor_source_id)
        target_index = (
            anchor_index if override.relation == "above" else anchor_index + 1
        )

        blended_index = round(current_index + weight * (target_index - current_index))
        blended_index = max(0, min(blended_index, len(order)))
        order.insert(blended_index, override.source_id)
        applied_override_by_item[override.source_id] = override

    merged: list[MergedPriorityItem] = []
    for displayed_rank, source_id in enumerate(order, start=1):
        item = items_by_id[source_id]
        merged.append(
            MergedPriorityItem(
                source_kind=item.source_kind,
                source_id=item.source_id,
                title=item.title,
                displayed_rank=displayed_rank,
                computed_rank=item.rank,
                overridden_from_computed=displayed_rank != item.rank,
                override=applied_override_by_item.get(source_id),
            )
        )
    return merged
