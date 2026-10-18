from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ChannelState = Literal["connected", "needs_reauth", "error", "off", "unknown"]


class ChannelStatusItem(BaseModel):
    channel_id: str
    channel_type: str
    handle: str | None
    display_name: str | None
    state: ChannelState
    last_sync_at: datetime | None
    push: bool


class ChannelStatusResponse(BaseModel):
    google_configured: bool
    channels: list[ChannelStatusItem]
