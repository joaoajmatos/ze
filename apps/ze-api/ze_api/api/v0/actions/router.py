from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ze_api.api.deps import require_api_key
from ze_api.api.v0.actions.schemas import ActionRecordPage, ActionSubjectType

router = APIRouter(
    prefix="/actions", tags=["actions"], dependencies=[Depends(require_api_key)]
)


@router.get(
    "",
    response_model=ActionRecordPage,
    operation_id="listActionRecords",
    summary="List what Ze did",
    description="List action-ledger records newest first, optionally for one goal, "
    "workflow, workflow run or workspace run. subject_type and subject_id go "
    "together. Pages by an opaque cursor.",
)
async def list_action_records(
    subject_type: ActionSubjectType | None = Query(default=None),
    subject_id: UUID | None = Query(default=None),
    since: datetime | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> ActionRecordPage:
    raise HTTPException(status_code=501, detail="Not implemented")
