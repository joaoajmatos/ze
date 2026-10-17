from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class PluginPageResponse(BaseModel):
    title: str
    tree: list[dict[str, Any]]


class ReminderItem(BaseModel):
    id: str
    label: str
    fire_at: datetime
    sent_at: datetime | None
    status: Literal["upcoming", "overdue", "fired"]
