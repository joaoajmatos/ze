from __future__ import annotations

import re
from typing import Literal
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationInfo,
    field_validator,
)


PushClassLiteral = Literal["requested", "accountability", "discretionary"]
DeliveryLiteral = Literal["delivered", "held", "released", "suppressed", "failed"]


class NotificationItem(BaseModel):
    id: str
    event_type: str
    source: str
    title: str
    body: str
    target_type: str | None
    target_id: str | None
    target_parent_id: str | None
    created_at: datetime
    read: bool
    push_class: str
    urgency: str
    delivery: str
    delivered_at: datetime | None


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
    next_cursor: str | None


class UnreadCountResponse(BaseModel):
    count: int


class MarkAllReadResponse(BaseModel):
    marked: int


_QUIET_HOURS_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class QuietHoursResponse(BaseModel):
    enabled: bool
    start: str | None
    end: str | None
    timezone: str | None
    active_now: bool


class AttentionBudgetResponse(BaseModel):
    used: int
    max_per_day: int
    remaining: int
    window_hours: float
    next_slot_at: datetime | None
    held_count: int
    quiet_hours_active: bool


class QuietHoursUpdate(BaseModel):
    model_config = ConfigDict(validate_default=True)

    enabled: bool
    start: str | None = None
    end: str | None = None
    timezone: str | None = None

    @field_validator("start", "end")
    @classmethod
    def _validate_time(cls, value: str | None, info: ValidationInfo) -> str | None:
        enabled = bool(info.data.get("enabled"))
        if value is None:
            if enabled:
                raise ValueError("required when quiet hours are enabled")
            return None
        if not _QUIET_HOURS_TIME_RE.match(value):
            raise ValueError("must be HH:MM in 24-hour time")
        if info.field_name == "end" and enabled and info.data.get("start") == value:
            raise ValueError("start and end must differ")
        return value

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            if info.data.get("enabled"):
                raise ValueError("required when quiet hours are enabled")
            return None
        try:
            ZoneInfo(value)
        except Exception:
            raise ValueError("must be a valid IANA timezone") from None
        return value
