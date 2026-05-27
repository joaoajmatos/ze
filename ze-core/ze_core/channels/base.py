from __future__ import annotations

from abc import ABC, abstractmethod

from ze_core.channels.types import Message, SentMessage, Thread


class Channel(ABC):
    channel_type: str

    @abstractmethod
    async def send(self, message: Message) -> SentMessage: ...

    @abstractmethod
    async def get_thread(self, thread_id: str) -> Thread: ...

    @abstractmethod
    async def poll_replies(self, sent: SentMessage) -> list[Thread]: ...
