from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ze_api.api.deps import require_api_key
from ze_api.api.v0.collisions.schemas import CollisionLogEntrySchema

router = APIRouter(
    prefix="/collisions", tags=["collisions"], dependencies=[Depends(require_api_key)]
)


@router.get(
    "",
    response_model=list[CollisionLogEntrySchema],
    operation_id="listCollisions",
    summary="List logged contribution collisions",
    description="List cross-function contribution collisions detected by the collision "
    "seam. Collisions are logged, never blocked or resolved.",
)
async def list_collisions(
    entity_id: UUID | None = Query(default=None),
    source_function: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[CollisionLogEntrySchema]:
    raise HTTPException(status_code=501, detail="Not implemented")
