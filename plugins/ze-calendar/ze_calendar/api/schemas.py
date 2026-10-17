from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ReminderItem(BaseModel):
    id: str
    label: str
    fire_at: datetime
    sent_at: datetime | None
    status: Literal["upcoming", "overdue", "fired"]
