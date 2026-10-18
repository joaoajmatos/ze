from __future__ import annotations

from uuid import UUID as UUIDType

from typing import Literal

from pydantic import (
    BaseModel,
)


LoopStateName = Literal["suspected", "active", "drifting", "closed", "dropped"]


class LoopListItem(BaseModel):
    id: UUIDType
    title: str
    state: str
    claim_kind: str
    provenance: str
    confidence: float
    drift_rationale: str | None
    goal_id: UUIDType | None
    reminder_id: UUIDType | None
    confidence_prior: float | None
    confidence_changed_at: str | None
    drift_deadline: str | None
    confirmed_at: str | None
    created_at: str | None
    updated_at: str | None
    promoted: bool
    source_inflows: list[str]


class LoopTransitionResponse(BaseModel):
    id: UUIDType
    state: str
    confidence: float
