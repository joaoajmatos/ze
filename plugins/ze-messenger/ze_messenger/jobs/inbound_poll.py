from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ze_google import is_auth_failure
from ze_logging import get_logger
from ze_personal.channels.types import PollOutcome, UserChannel

_log = get_logger(__name__)


class InboundPollingJob:
    job_id = "inbound_poll"

    def __init__(
        self,
        registry: object,  # ChannelRegistry — avoid circular at import time
        watermark_store: object,  # ChannelWatermarkStore
        user_channel_store: object,  # UserChannelStore
        processor: object,  # InboundMessageProcessor
    ) -> None:
        self._registry = registry
        self._watermarks = watermark_store
        self._user_channels = user_channel_store
        self._processor = processor

    async def run(self) -> None:
        all_user_channels = await self._user_channels.list_all()
        registered = {uc.channel_id for uc in all_user_channels}
        enabled = {uc.channel_id for uc in all_user_channels if uc.poll_enabled}

        for channel in self._registry.inbound_channels():
            # Skip channels that are registered but explicitly disabled
            if channel.channel_id in registered and channel.channel_id not in enabled:
                continue
            if channel.supports_push:
                continue  # Phase 86 handles these via webhook
            await self._poll(channel)

    async def _poll(self, channel: object) -> None:
        try:
            if hasattr(channel, "_resolve_user_email"):
                await channel._resolve_user_email()
            since = await self._watermarks.get(channel.channel_id)
            messages = await channel.poll_new_messages(since=since)
        except Exception as exc:
            _log.warning(
                "inbound_poll_failed",
                channel_id=channel.channel_id,
                error=str(exc),
            )
            outcome = (
                PollOutcome.AUTH_FAILED if is_auth_failure(exc) else PollOutcome.FAILED
            )
            await self._record_failure(channel, outcome)
            return

        for msg in messages:
            try:
                await self._processor.process(msg, channel_id=channel.channel_id)
            except Exception:
                _log.warning(
                    "inbound_message_process_failed",
                    channel_id=channel.channel_id,
                    message_id=getattr(msg, "message_id", "?"),
                )

        # Auto-register channel in user_channels on first successful poll
        try:
            await self._user_channels.upsert(self._user_channel(channel))
            await self._watermarks.set(channel.channel_id, datetime.now(timezone.utc))
        except Exception as exc:
            _log.warning(
                "inbound_poll_register_failed",
                channel_id=channel.channel_id,
                error=str(exc),
            )
            await self._record_failure(channel, PollOutcome.FAILED)
            return
        await self._record_success(channel)

    @staticmethod
    def _user_channel(channel: object) -> UserChannel:
        handle = getattr(channel, "_user_email", None) or channel.channel_id
        return UserChannel(
            id=uuid4(),
            channel_id=channel.channel_id,
            channel_type=channel.channel_type.value,
            handle=handle,
            display_name=None,
            is_default_outbound=False,
            poll_enabled=True,
            created_at=datetime.now(timezone.utc),
        )

    async def _record_failure(self, channel: object, outcome: PollOutcome) -> None:
        try:
            channel_id = await self._failure_key(channel)
            await self._watermarks.record_outcome(
                channel_id, outcome, datetime.now(timezone.utc)
            )
        except Exception as exc:
            _log.warning(
                "inbound_poll_outcome_failed",
                channel_id=channel.channel_id,
                error=str(exc),
            )

    async def _failure_key(self, channel: object) -> str:
        """The row a failed poll is recorded on.

        With the account unresolved the channel id is the bare type value. When one
        keyed row of that type already exists (after a restart with an expired
        token), the failure goes on that row so no second row appears. Otherwise the
        bare row is inserted if absent, never overwriting a known address.
        """
        bare_key = channel.channel_type.value
        if channel.channel_id == bare_key:
            keyed = [
                uc
                for uc in await self._user_channels.list_all()
                if uc.channel_type == bare_key and uc.channel_id != bare_key
            ]
            if len(keyed) == 1:
                return keyed[0].channel_id
        await self._user_channels.ensure(self._user_channel(channel))
        return channel.channel_id

    async def _record_success(self, channel: object) -> None:
        try:
            await self._watermarks.record_outcome(
                channel.channel_id, PollOutcome.OK, datetime.now(timezone.utc)
            )
            bare_key = channel.channel_type.value
            if channel.channel_id != bare_key:
                await self._user_channels.drop_unkeyed(bare_key)
        except Exception as exc:
            _log.warning(
                "inbound_poll_outcome_failed",
                channel_id=channel.channel_id,
                error=str(exc),
            )
