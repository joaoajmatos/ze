from __future__ import annotations

import base64
import binascii
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ze_api.api.deps import get_action_record_store, require_api_key
from ze_api.api.v0.actions.schemas import (
    ActionRecordItem,
    ActionRecordPage,
    ActionSubjectType,
    ActionTouched,
)
from ze_memory.action_records.store import ActionRecordStore
from ze_memory.action_records.types import ActionRecord, ActionSubjectKind

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
    store: ActionRecordStore = Depends(get_action_record_store),
) -> ActionRecordPage:
    if (subject_type is None) != (subject_id is None):
        raise HTTPException(
            status_code=422,
            detail="subject_type and subject_id must be given together",
        )
    kind = ActionSubjectKind(subject_type) if subject_type is not None else None
    records = await store.list_by_subject(
        kind=kind,
        subject_id=subject_id,
        since=since,
        cursor=_decode_cursor(cursor) if cursor is not None else None,
        limit=limit + 1,
    )
    page, more = records[:limit], len(records) > limit
    return ActionRecordPage(
        items=[_item(record) for record in page],
        next_cursor=_encode_cursor(page[-1]) if more else None,
    )


def _encode_cursor(record: ActionRecord) -> str:
    raw = f"{record.occurred_at.isoformat()}|{record.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        stamp, record_id = raw.split("|")
        at = datetime.fromisoformat(stamp)
        if at.tzinfo is None:
            raise ValueError("naive timestamp")
        return at, UUID(record_id)
    except (binascii.Error, ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=422, detail="invalid cursor") from None


def _item(record: ActionRecord) -> ActionRecordItem:
    return ActionRecordItem(
        id=record.id,
        action_type=record.action_type,
        actor=record.actor,
        producer_plugin=record.producer_plugin,
        lifecycle=record.lifecycle.value,
        outcome=record.outcome.value if record.outcome is not None else None,
        summary=record.summary,
        touched=ActionTouched(
            domain=record.authoritative_ref.domain,
            record_id=record.authoritative_ref.record_id,
        ),
        occurred_at=record.occurred_at,
        failure_code=record.failure_code,
    )
