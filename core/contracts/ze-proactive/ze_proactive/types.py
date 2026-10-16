from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Literal

PushClass = Literal["requested", "accountability", "discretionary"]
Urgency = Literal["low", "normal", "high"]
Delivery = Literal["delivered", "held", "released", "suppressed", "failed"]
PushOutcome = Literal[
    "delivered", "held", "suppressed_budget", "duplicate", "deduped", "failed"
]


@dataclass(frozen=True)
class PushKind:
    """One kind of proactive push. Declared once, at module level."""

    event_type: str
    push_class: PushClass
    urgency: Urgency
    source: str
    # False when the thing pushed is already in the conversation (a confirmation
    # card): the push rings the bell and buzzes, but adds no chat message.
    in_chat: bool = True

    def __post_init__(self) -> None:
        from ze_proactive.push_kinds import register

        register(self)


@dataclass(frozen=True)
class QuietHoursSetting:
    enabled: bool
    start: time | None
    end: time | None
    timezone: str | None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class JobRun:
    job_id: str
    last_started_at: datetime
    last_finished_at: datetime | None
    last_status: Literal["running", "ok", "error"]


@dataclass
class NotificationRow:
    """Persisted `notifications` table row (ze-proactive owned)."""

    id: str
    event_type: str
    source: str
    title: str
    body: str
    target_type: str | None
    target_id: str | None
    created_at: datetime
    read_at: datetime | None
    push_class: str = "accountability"
    urgency: str = "normal"
    format: str = "text"
    actions: list[dict] | None = None
    delivery: str = "delivered"
    delivered_at: datetime | None = None


@dataclass
class Notification:
    """Wire representation — REST list item / `notification` WS frame payload."""

    id: str
    event_type: str
    source: str
    title: str
    body: str
    target_type: str | None
    target_id: str | None
    created_at: datetime
    read: bool
    push_class: str = "accountability"
    urgency: str = "normal"
    delivery: str = "delivered"
