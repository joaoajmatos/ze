from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class HeldWriteStatus(StrEnum):
    OPEN = "open"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass
class HeldWrite:
    request_id: str
    source: str
    owner_ref: str
    items: list[dict] = field(default_factory=list)
    payload: dict = field(default_factory=dict)
    expires_at: datetime | None = None
    status: HeldWriteStatus = HeldWriteStatus.OPEN
    created_at: datetime | None = None
    decided_at: datetime | None = None
