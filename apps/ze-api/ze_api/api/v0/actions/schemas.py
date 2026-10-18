from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID as UUIDType

from pydantic import BaseModel

ActionSubjectType = Literal["goal", "workflow", "workflow_run", "workspace_run"]


class ActionTouched(BaseModel):
    domain: str
    record_id: str


class ActionRecordItem(BaseModel):
    id: UUIDType
    action_type: str
    actor: str
    producer_plugin: str
    lifecycle: str
    outcome: str | None
    summary: str
    touched: ActionTouched
    occurred_at: datetime
    failure_code: str | None


class ActionRecordPage(BaseModel):
    items: list[ActionRecordItem]
    next_cursor: str | None
