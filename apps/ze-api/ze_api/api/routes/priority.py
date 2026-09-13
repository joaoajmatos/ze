from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ze_api.api.dependencies import (
    get_collision_store,
    get_nli_client,
    get_priority_override_store,
    get_priority_view,
    require_api_key,
)
from ze_api.api.schemas import (
    PriorityOverrideRequestSchema,
    PrioritySnapshotItem,
)
from ze_collision.store import CollisionLogStore
from ze_priority import rest as priority_rest
from ze_priority.errors import (
    PriorityOverrideNotFoundError,
    StaleReprioritizationTargetError,
)
from ze_priority.store import PriorityOverrideStore
from ze_priority.types import PriorityOverrideRequest
from ze_priority.view import PriorityView

router = APIRouter(
    prefix="/priority", tags=["priority"], dependencies=[Depends(require_api_key)]
)


@router.get(
    "/snapshot",
    response_model=list[PrioritySnapshotItem],
    operation_id="getPrioritySnapshot",
    summary="Get the current priority snapshot",
    description="Return PriorityView's ranked loops, stuck/near-gate goals, and "
    "non-stale hypotheses, merged with any active user reprioritizations "
    "(FR-001, FR-008, FR-009, FR-010).",
)
async def get_priority_snapshot(
    priority_view: PriorityView = Depends(get_priority_view),
    override_store: PriorityOverrideStore = Depends(get_priority_override_store),
) -> list[PrioritySnapshotItem]:
    snapshot = await priority_rest.get_snapshot(priority_view, override_store)
    return [PrioritySnapshotItem.from_merged_item(item) for item in snapshot]


@router.post(
    "/override",
    response_model=PrioritySnapshotItem,
    operation_id="submitPriorityOverride",
    summary="Submit a user reprioritization",
    description="Drag-path entry point (FR-002). Submits a user-stated Contribution "
    "through the validated write path (FR-004/FR-005) targeting the named anchor "
    "item. Superseding an existing override for the same item is implicit (FR-012).",
)
async def submit_priority_override(
    request: PriorityOverrideRequestSchema,
    priority_view: PriorityView = Depends(get_priority_view),
    override_store: PriorityOverrideStore = Depends(get_priority_override_store),
    collision_store: CollisionLogStore = Depends(get_collision_store),
    nli_client=Depends(get_nli_client),
) -> PrioritySnapshotItem:
    try:
        row = await priority_rest.submit_override(
            PriorityOverrideRequest(**request.model_dump()),
            priority_view=priority_view,
            override_store=override_store,
            collision_store=collision_store,
            nli_client=nli_client,
        )
    except StaleReprioritizationTargetError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return PrioritySnapshotItem.from_merged_item(row)


@router.post(
    "/override/{override_id}/unpin",
    response_model=PrioritySnapshotItem,
    operation_id="unpinPriorityOverride",
    summary="Unpin a priority override",
    description="Clears the pinned flag on an active override, converting it back "
    "to a fresh decaying override starting from now (FR-009's 'until the user "
    "unpins it' path).",
)
async def unpin_priority_override(
    override_id: UUID,
    priority_view: PriorityView = Depends(get_priority_view),
    override_store: PriorityOverrideStore = Depends(get_priority_override_store),
) -> PrioritySnapshotItem:
    try:
        row = await priority_rest.unpin_override(
            override_id, priority_view=priority_view, override_store=override_store
        )
    except (PriorityOverrideNotFoundError, StaleReprioritizationTargetError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return PrioritySnapshotItem.from_merged_item(row)
