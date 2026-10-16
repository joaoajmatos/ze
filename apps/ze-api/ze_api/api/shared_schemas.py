from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
)

RollbackOutcomeLiteral = Literal["undone", "failed", "not_attempted"]


RollbackStateLiteral = Literal[
    "partial",
    "rolled_back_awaiting_confirmation",
    "rolled_back_retry_failed",
    "superseded",
]


class RollbackEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entry_id: str
    tool: str
    effect_phrase: str
    outcome: RollbackOutcomeLiteral
    at: str | None = None
    failure_code: str | None = None


class RollbackRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state: RollbackStateLiteral
    entries: list[RollbackEntryResponse] = []
    replaced_by: str | None = None


class ErrorDetail(BaseModel):
    detail: str | list[dict[str, Any]]
