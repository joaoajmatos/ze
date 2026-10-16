from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
)


class ConfirmItemOut(BaseModel):
    item_id: str
    agent: str
    tool: str | None = None
    effect_phrase: str
    summary: str
    conflict: str | None = None
    editable_field: str | None = None
    proposed_text: str | None = None


class HeldWriteOut(BaseModel):
    request_id: str
    source: Literal["workflow", "goal"]
    source_name: str
    owner_ref: str
    items: list[ConfirmItemOut]
    status: Literal["open", "approved", "denied", "expired"]
    created_at: str | None = None
    expires_at: str | None = None


class HeldWriteListResponse(BaseModel):
    items: list[HeldWriteOut]


class HeldWriteDecisionIn(BaseModel):
    choice: Literal["approve", "deny"]
    edits: dict[str, str] = {}
