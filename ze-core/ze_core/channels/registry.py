from __future__ import annotations

from ze_core.channels.base import Channel
from ze_core.errors import ChannelNotFoundError


class ChannelRegistry:
    def __init__(self) -> None:
        self._channels: dict[str, Channel] = {}

    def register(self, channel: Channel) -> None:
        self._channels[channel.channel_type] = channel

    def get(self, channel_type: str) -> Channel:
        try:
            return self._channels[channel_type]
        except KeyError:
            raise ChannelNotFoundError(
                f"No channel registered for type {channel_type!r}"
            )

    def all(self) -> list[Channel]:
        return list(self._channels.values())

    def __contains__(self, channel_type: str) -> bool:
        return channel_type in self._channels
