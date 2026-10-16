from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
)


class SessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str | None
    preview: str | None
    title_source: Literal["user", "generated"] | None = None
    created_at: datetime
    last_active_at: datetime


class SessionListResponse(BaseModel):
    items: list[SessionSchema]
    next_before: datetime | None


class SessionSearchResult(BaseModel):
    id: str
    title: str | None
    preview: str | None
    title_source: Literal["user", "generated"] | None = None
    created_at: datetime
    last_active_at: datetime
    match_source: Literal["message", "metadata", "summary"]
    snippet: str | None
    rank: float
