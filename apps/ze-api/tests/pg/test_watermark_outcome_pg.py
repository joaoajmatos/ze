from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from ze_personal.channels.types import PollOutcome, UserChannel
from ze_personal.channels.user_channel_store import UserChannelStore
from ze_personal.channels.watermark_store import ChannelWatermarkStore

pytestmark = pytest.mark.pg


def _channel(channel_id: str, handle: str) -> UserChannel:
    return UserChannel(
        id=uuid4(),
        channel_id=channel_id,
        channel_type="email",
        handle=handle,
        display_name=None,
        is_default_outbound=False,
        poll_enabled=True,
        created_at=datetime.now(timezone.utc),
    )


async def _reset(pg_pool) -> None:
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM user_channel_watermarks")
        await conn.execute("DELETE FROM user_channels")


async def test_outcome_insert_keeps_the_lookback_start(pg_pool):
    await _reset(pg_pool)
    await UserChannelStore(pg_pool).ensure(_channel("email", "email"))
    store = ChannelWatermarkStore(pg_pool)
    now = datetime.now(timezone.utc)

    await store.record_outcome("email", PollOutcome.AUTH_FAILED, now)

    watermark = await store.get("email")
    assert abs((now - watermark) - timedelta(hours=24)) < timedelta(minutes=1)
    status = (await store.get_status_many(["email"]))["email"]
    assert status.last_outcome is PollOutcome.AUTH_FAILED


async def test_outcome_update_leaves_last_polled_at_alone(pg_pool):
    await _reset(pg_pool)
    await UserChannelStore(pg_pool).ensure(_channel("gmail:me@x", "me@x"))
    store = ChannelWatermarkStore(pg_pool)
    polled = datetime.now(timezone.utc) - timedelta(hours=3)
    await store.set("gmail:me@x", polled)

    await store.record_outcome("gmail:me@x", PollOutcome.OK, datetime.now(timezone.utc))

    assert await store.get("gmail:me@x") == polled


async def test_fail_reauth_succeed_leaves_one_connected_gmail_row(pg_pool):
    await _reset(pg_pool)
    users = UserChannelStore(pg_pool)
    marks = ChannelWatermarkStore(pg_pool)
    now = datetime.now(timezone.utc)

    await users.ensure(_channel("email", "email"))
    await marks.record_outcome("email", PollOutcome.AUTH_FAILED, now)

    await users.upsert(_channel("gmail:me@x", "me@x"))
    await marks.set("gmail:me@x", now)
    await marks.record_outcome("gmail:me@x", PollOutcome.OK, now)
    await users.drop_unkeyed("email")

    rows = await users.list_all()
    assert [r.channel_id for r in rows] == ["gmail:me@x"]
    status = await marks.get_status_many(["gmail:me@x", "email"])
    assert status["gmail:me@x"].last_outcome is PollOutcome.OK
    assert status["email"].last_outcome is None


async def test_failure_after_restart_leaves_one_needs_reauth_row(pg_pool):
    from unittest.mock import AsyncMock, MagicMock

    from google.auth.exceptions import RefreshError
    from ze_communication.types import ChannelType
    from ze_messenger.jobs.inbound_poll import InboundPollingJob

    await _reset(pg_pool)
    users = UserChannelStore(pg_pool)
    marks = ChannelWatermarkStore(pg_pool)
    await users.upsert(_channel("gmail:me@x", "me@x"))
    await marks.set("gmail:me@x", datetime.now(timezone.utc))
    await marks.record_outcome("gmail:me@x", PollOutcome.OK, datetime.now(timezone.utc))

    channel = MagicMock()
    channel.channel_id = "email"
    channel.channel_type = ChannelType.EMAIL
    channel.supports_push = False
    channel._user_email = None
    channel._resolve_user_email = AsyncMock(side_effect=RefreshError("invalid_grant"))
    registry = MagicMock()
    registry.inbound_channels.return_value = [channel]
    job = InboundPollingJob(
        registry=registry,
        watermark_store=marks,
        user_channel_store=users,
        processor=AsyncMock(),
    )

    await job.run()

    rows = await users.list_all()
    assert [r.channel_id for r in rows] == ["gmail:me@x"]
    status = (await marks.get_status_many(["gmail:me@x"]))["gmail:me@x"]
    assert status.last_outcome is PollOutcome.AUTH_FAILED
