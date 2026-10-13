from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from ze_agents.nli import NLIClient
from ze_collision.store import CollisionLogStore

from ze_priority.errors import StaleReprioritizationTargetError
from ze_priority.merge import merge
from ze_priority.service import submit_reprioritization
from ze_priority.store import PriorityOverrideStore
from ze_priority.types import (
    MergedPriorityItem,
    PriorityOverrideRequest,
    PrioritySnapshotResult,
)
from ze_priority.view import PriorityView

UTC = timezone.utc


async def get_snapshot(
    priority_view: PriorityView, override_store: PriorityOverrideStore
) -> PrioritySnapshotResult:
    ranking = await priority_view.rank()
    overrides = await override_store.get_active()
    return PrioritySnapshotResult(
        items=merge(ranking, overrides, datetime.now(UTC)),
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
    override = await submit_reprioritization(
        request,
        priority_view=priority_view,
        override_store=override_store,
        collision_store=collision_store,
        nli_client=nli_client,
    )
    return await _snapshot_row_for(override.source_id, priority_view, override_store)


async def unpin_override(
    override_id: UUID,
    *,
    priority_view: PriorityView,
    override_store: PriorityOverrideStore,
) -> MergedPriorityItem:
    override = await override_store.unpin(override_id)
    return await _snapshot_row_for(override.source_id, priority_view, override_store)


async def _snapshot_row_for(
    source_id: UUID,
    priority_view: PriorityView,
    override_store: PriorityOverrideStore,
) -> MergedPriorityItem:
    snapshot = await get_snapshot(priority_view, override_store)
    for row in snapshot.items:
        if row.source_id == source_id:
            return row
    raise StaleReprioritizationTargetError(
        f"item {source_id} is no longer present in any PriorityView source list"
    )
