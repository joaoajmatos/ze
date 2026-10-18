from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


@dataclass
class UserChannel:
    id: UUID
    channel_id: str  # matches InboundChannel.channel_id
    channel_type: str  # ChannelType value
    handle: str  # user's address on this channel
    display_name: str | None
    is_default_outbound: bool
    poll_enabled: bool
    created_at: datetime


class PollOutcome(StrEnum):
    OK = "ok"
    AUTH_FAILED = "auth_failed"
    FAILED = "failed"


@dataclass(frozen=True)
class ChannelPollStatus:
    watermark: datetime | None
    last_outcome: PollOutcome | None
    last_outcome_at: datetime | None
