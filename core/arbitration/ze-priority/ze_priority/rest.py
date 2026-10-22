from __future__ import annotations

from uuid import UUID

from ze_agents.nli import NLIClient
from ze_collision.store import CollisionLogStore

from ze_priority.errors import StaleReprioritizationTargetError
from ze_priority.service import submit_reprioritization
from ze_priority.store import PriorityOverrideStore
from ze_priority.types import (
    MergedPriorityItem,
    PriorityOverrideRequest,
    PrioritySnapshotResult,
)
from ze_priority.view import PriorityView


async def get_snapshot(priority_view: PriorityView) -> PrioritySnapshotResult:
    ranking = await priority_view.rank()
    return PrioritySnapshotResult(
        items=[
            MergedPriorityItem(
                source_kind=item.source_kind,
                source_id=item.source_id,
                title=item.title,
                displayed_rank=item.rank,
                computed_rank=item.computed_rank,
                overridden_from_computed=item.rank != item.computed_rank,
                override=item.override,
            )
            for item in ranking.items
        ],
        sources_failed=tuple(sorted(ranking.sources_failed)),
    )


async def submit_override(
    request: PriorityOverrideRequest,
    *,
    priority_view: PriorityView,
    override_store: PriorityOverrideStore,
    collision_store: CollisionLogStore | None = None,
    nli_client: NLIClient | None = None,
) -> MergedPriorityItem:
    override, _superseded_id = await submit_reprioritization(
        request,
        priority_view=priority_view,
        override_store=override_store,
        collision_store=collision_store,
        nli_client=nli_client,
    )
    return await _snapshot_row_for(override.source_id, priority_view)


async def unpin_override(
    override_id: UUID,
    *,
    priority_view: PriorityView,
    override_store: PriorityOverrideStore,
) -> MergedPriorityItem:
    override = await override_store.unpin(override_id)
    return await _snapshot_row_for(override.source_id, priority_view)


async def _snapshot_row_for(
    source_id: UUID, priority_view: PriorityView
) -> MergedPriorityItem:
    snapshot = await get_snapshot(priority_view)
    for row in snapshot.items:
        if row.source_id == source_id:
            return row
    raise StaleReprioritizationTargetError(
        f"item {source_id} is no longer present in any PriorityView source list"
    )
