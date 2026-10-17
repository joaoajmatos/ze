from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
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
class BudgetStatus:
    """The rolling-window attention budget as the governor counts it."""

    max_per_day: int
    window_hours: float
    counted_at: tuple[datetime, ...]  # sent_at of every counted claim, ascending

    @property
    def used(self) -> int:
        return len(self.counted_at)

    @property
    def remaining(self) -> int:
        return max(0, self.max_per_day - self.used)

    @property
    def next_slot_at(self) -> datetime | None:
        # One slot opens when used - max + 1 claims have left the window.
        if self.remaining > 0 or self.max_per_day == 0:
            return None
        return self.counted_at[self.used - self.max_per_day] + timedelta(
            hours=self.window_hours
        )


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
    target_parent_id: str | None = None


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
    target_parent_id: str | None = None
