from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ze_api.api.datetimes import require_aware
from ze_api.api.deps import get_collision_store, require_api_key
from ze_api.api.v0.collisions.schemas import CollisionLogEntrySchema
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
    "seam. Collisions are logged, never blocked or resolved. `since` and `until` need "
    "a timezone offset (use Z or %2B00:00 in a URL); `since` after `until` returns an empty list.",
)
async def list_collisions(
    entity_id: UUID | None = Query(default=None),
    source_function: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    store: CollisionLogStore = Depends(get_collision_store),
) -> list[CollisionLogEntrySchema]:
    require_aware(since=since, until=until)
    sf = None
    if source_function:
        try:
            sf = SourceFunction(source_function)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown source_function {source_function!r}",
            )
    if since and until and since > until:
        return []
    entries = await collision_rest.list_collisions(
        store,
        entity_id=entity_id,
        source_function=sf,
        since=since,
        until=until,
        limit=limit,
    )
    return [CollisionLogEntrySchema.from_entry(e) for e in entries]
