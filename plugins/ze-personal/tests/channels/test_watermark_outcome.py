from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from ze_personal.channels.types import ChannelPollStatus, PollOutcome
from ze_personal.channels.watermark_store import ChannelWatermarkStore


def _make_pool(conn):
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=cm)
    return pool


def _row(**values):
    row = MagicMock()
    row.__getitem__ = lambda self, k: values[k]
    return row


async def test_record_outcome_updates_existing_row_without_moving_the_watermark():
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    store = ChannelWatermarkStore(pool=_make_pool(conn))
    at = datetime.now(timezone.utc)

    await store.record_outcome("gmail:me@x", PollOutcome.AUTH_FAILED, at)

    conn.execute.assert_called_once()
    sql, *args = conn.execute.call_args[0]
    assert sql.lstrip().startswith("UPDATE user_channel_watermarks")
    assert "last_outcome" in sql and "last_outcome_at" in sql
    assert "last_polled_at" not in sql
    assert args == ["gmail:me@x", "auth_failed", at]


async def test_record_outcome_inserts_the_lookback_start_when_no_row():
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=["UPDATE 0", "INSERT 0 1"])
    store = ChannelWatermarkStore(pool=_make_pool(conn))
    at = datetime.now(timezone.utc)

    await store.record_outcome("email", PollOutcome.FAILED, at)

    assert conn.execute.call_count == 2
    sql, channel_id, polled_at, outcome, outcome_at = conn.execute.call_args_list[1][0]
    assert sql.lstrip().startswith("INSERT INTO user_channel_watermarks")
    assert channel_id == "email"
    assert outcome == "failed" and outcome_at == at
    expected = datetime.now(timezone.utc) - timedelta(
        hours=ChannelWatermarkStore.DEFAULT_LOOKBACK_HOURS
    )
    assert abs((polled_at - expected).total_seconds()) < 5


async def test_get_after_failed_insert_returns_the_lookback_start():
    conn = AsyncMock()
    start = datetime.now(timezone.utc) - timedelta(hours=24)
    conn.execute = AsyncMock(side_effect=["UPDATE 0", "INSERT 0 1"])
    conn.fetchrow = AsyncMock(return_value=_row(last_polled_at=start))
    store = ChannelWatermarkStore(pool=_make_pool(conn))

    await store.record_outcome("email", PollOutcome.FAILED, datetime.now(timezone.utc))

    assert await store.get("email") == start


async def test_get_status_many_returns_one_entry_per_id_with_nulls_for_unknown():
    at = datetime.now(timezone.utc)
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            _row(
                channel_id="gmail:me@x",
                last_polled_at=at,
                last_outcome="ok",
                last_outcome_at=at,
            )
        ]
    )
    store = ChannelWatermarkStore(pool=_make_pool(conn))

    result = await store.get_status_many(["gmail:me@x", "gmail:other@x"])

    assert result == {
        "gmail:me@x": ChannelPollStatus(
            watermark=at, last_outcome=PollOutcome.OK, last_outcome_at=at
        ),
        "gmail:other@x": ChannelPollStatus(
            watermark=None, last_outcome=None, last_outcome_at=None
        ),
    }


async def test_get_status_many_with_no_ids_skips_the_query():
    conn = AsyncMock()
    store = ChannelWatermarkStore(pool=_make_pool(conn))

    assert await store.get_status_many([]) == {}
    conn.fetch.assert_not_called()
