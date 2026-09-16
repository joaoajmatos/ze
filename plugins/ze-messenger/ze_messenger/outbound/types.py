from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4


class OutboundSendOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


@dataclass
class OutboundSend:
    message_id: str
    thread_id: str
    channel_type: str
    channel_id: str
    sent_at: datetime
    outcome: OutboundSendOutcome
    id: UUID | None = None
    failure_code: str | None = None
    ledger_idempotency_key: str | None = None
    ledger_pending: bool = False

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = uuid4()
