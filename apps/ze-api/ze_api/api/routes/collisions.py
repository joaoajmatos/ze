from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ze_api.api.dependencies import get_collision_store, require_api_key
from ze_api.api.schemas import CollisionLogEntrySchema
from ze_collision import rest as collision_rest
from ze_collision.store import CollisionLogStore
from ze_plugin.contribution import SourceFunction

router = APIRouter(
    prefix="/collisions", tags=["collisions"], dependencies=[Depends(require_api_key)]
)


@router.get(
    "",
    response_model=list[CollisionLogEntrySchema],
    operation_id="listCollisions",
    summary="List logged contribution collisions",
    description="List cross-function contribution collisions detected by the collision "
    "seam (FR-009) — collisions are logged, never blocked or resolved.",
)
async def list_collisions(
    entity_id: UUID | None = Query(default=None),
    source_function: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    store: CollisionLogStore = Depends(get_collision_store),
) -> list[CollisionLogEntrySchema]:
    sf = SourceFunction(source_function) if source_function else None
    entries = await collision_rest.list_collisions(
        store,
        entity_id=entity_id,
        source_function=sf,
        since=since,
        until=until,
        limit=limit,
    )
    return [CollisionLogEntrySchema.from_entry(e) for e in entries]
