from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ze_api.api.deps import (
    get_container,
    require_api_key,
)
from ze_api.api.openapi import OPENAPI_RESPONSES_422
from ze_api.api.schemas import (
    EntityDetailResponse,
    FactReviewRequest,
    MemoryActivityResponse,
    MemoryFeedItem,
    MemoryFeedResponse,
    MemoryGraphResponse,
    TimelineBoundsResponse,
)
from ze_memory import admin as memory_admin

router = APIRouter(prefix="/memory", tags=["memory"], dependencies=[Depends(require_api_key)])


@router.get(
    "/feed",
    response_model=MemoryFeedResponse,
    operation_id="getMemoryFeed",
    summary="Memory feed",
    description=(
        "Reverse-chronological stream of facts and episodes. "
        "Cursor-paginated via the `before` timestamp. "
        "Filter by `type` (fact/episode/all) and `agent`. "
        "Pass `as_of` to get a point-in-time snapshot of Ze's memory."
    ),
)
async def get_memory_feed(
    limit: int = Query(default=50, ge=1, le=200, description="Max items per page"),
    before: datetime | None = Query(
        default=None, description="Return items older than this timestamp"
    ),
    type: Literal["fact", "episode", "all"] = Query(
        default="all", description="Filter by item type"
    ),
    agent: str | None = Query(
        default=None, description="Filter by originating agent name"
    ),
    as_of: datetime | None = Query(
        default=None, description="Return only items that existed at this point in time"
    ),
    include_totals: bool = Query(
        default=False,
        description="Include total fact/episode counts (auto-enabled on first page without cursor)",
    ),
    container=Depends(get_container),
) -> MemoryFeedResponse:
    result = await memory_admin.get_memory_feed(
        container.pool,
        limit=limit,
        before=before,
        type_filter=type,
        agent_filter=agent,
        as_of=as_of,
        include_totals=include_totals,
    )
    return MemoryFeedResponse.model_validate(result)


@router.get(
    "/timeline-bounds",
    response_model=TimelineBoundsResponse,
    operation_id="getMemoryTimelineBounds",
    summary="Memory timeline bounds",
    description=(
        "Returns the earliest and latest memory timestamps. "
        "Use to configure the date scrubber range on the memory feed page."
    ),
)
async def get_memory_timeline_bounds(
    container=Depends(get_container),
) -> TimelineBoundsResponse:
    result = await memory_admin.get_memory_timeline_bounds(container.pool)
    return TimelineBoundsResponse.model_validate(result)


@router.get(
    "/activity",
    response_model=MemoryActivityResponse,
    operation_id="getMemoryActivity",
    summary="Memory activity by day",
    description=(
        "Per-day counts of facts + episodes created between `start` and `end`. "
        "Use to render an activity density overlay on the timeline scrubber."
    ),
)
async def get_memory_activity(
    start: datetime = Query(description="Start of range (inclusive)"),
    end: datetime = Query(description="End of range (exclusive)"),
    container=Depends(get_container),
) -> MemoryActivityResponse:
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    result = await memory_admin.get_memory_activity(
        container.pool, start=start, end=end
    )
    return MemoryActivityResponse.model_validate(result)


@router.post(
    "/facts/review",
    response_model=list[MemoryFeedItem],
    operation_id="reviewFacts",
    summary="Review memory facts",
    description=(
        "Apply confirm, reject, or edit actions to memory facts. Confirm and edit set "
        "`reviewed=true`; reject deletes the row. Edit requires `value` in the action."
    ),
    responses=OPENAPI_RESPONSES_422,
)
async def review_facts(
    body: FactReviewRequest,
    container=Depends(get_container),
) -> list[MemoryFeedItem]:
    for action in body.actions:
        if action.action == "edit" and action.value is None:
            raise HTTPException(
                status_code=422, detail="value required for edit action"
            )
    updated = await memory_admin.review_facts(container.pool, body.actions)
    return [MemoryFeedItem.model_validate(r) for r in updated]


@router.get(
    "/graph",
    response_model=MemoryGraphResponse,
    operation_id="getMemoryGraph",
    summary="Memory entity graph",
    description=(
        "Returns top-N entities by relationship count, plus all entity-to-entity "
        "edges between them. Pass `seed_id` to expand from a specific entity."
    ),
)
async def get_memory_graph(
    limit: int = Query(default=50, ge=1, le=200, description="Max entities to return"),
    entity_type: str | None = Query(default=None, description="Filter by entity type"),
    seed_id: UUID | None = Query(
        default=None, description="Expand 1-hop from this entity"
    ),
    container=Depends(get_container),
) -> MemoryGraphResponse:
    result = await memory_admin.get_memory_graph(
        container.pool,
        limit=limit,
        entity_type=entity_type,
        seed_id=seed_id,
    )
    return MemoryGraphResponse.model_validate(result)


@router.get(
    "/graph/entity/{entity_id}",
    response_model=EntityDetailResponse,
    operation_id="getEntityDetail",
    summary="Entity detail",
    description=(
        "Facts, episodes, and 1-hop neighbours for a selected entity. "
        "Use `neighbours` and `neighbour_edges` to expand the graph."
    ),
)
async def get_entity_detail(
    entity_id: UUID,
    container=Depends(get_container),
) -> EntityDetailResponse:
    result = await memory_admin.get_entity_detail(container.pool, entity_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return EntityDetailResponse.model_validate(result)
