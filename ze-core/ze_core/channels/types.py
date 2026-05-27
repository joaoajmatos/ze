from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    content: str
    channel_type: str
    recipient: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SentMessage:
    message_id: str
    channel_type: str
    recipient: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ThreadMessage:
    message_id: str
    sender: str
    content: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Thread:
    thread_id: str
    channel_type: str
    messages: list[ThreadMessage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelHandle:
    channel_type: str
    address: str
    metadata: dict[str, Any] = field(default_factory=dict)
