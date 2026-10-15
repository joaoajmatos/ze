from __future__ import annotations

from datetime import datetime, time, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_proactive.quiet_hours import InterruptionSettingsStore, is_active
from ze_proactive.types import QuietHoursSetting


def _setting(start, end, tz="UTC", enabled=True):
    return QuietHoursSetting(
        enabled=enabled, start=start, end=end, timezone=tz, updated_at=None
    )


def _utc(h, m=0, day=(2026, 6, 15)):
    return datetime(*day, h, m, tzinfo=timezone.utc)


def test_disabled_is_inactive():
    assert not is_active(_setting(time(0), time(23), enabled=False), _utc(12))


def test_missing_fields_inactive():
    assert not is_active(QuietHoursSetting(True, None, None, None), _utc(12))


@pytest.mark.parametrize(
    "h,m,expected",
    [(12, 59, False), (13, 0, True), (14, 59, True), (15, 0, False)],
)
def test_same_day_window(h, m, expected):
    assert is_active(_setting(time(13), time(15)), _utc(h, m)) is expected


@pytest.mark.parametrize(
    "h,m,expected",
    [(22, 59, False), (23, 0, True), (2, 0, True), (7, 59, True), (8, 0, False)],
)
def test_overnight_window(h, m, expected):
    assert is_active(_setting(time(23), time(8)), _utc(h, m)) is expected


@pytest.mark.parametrize(
    "now,expected",
    [
        # 2026-03-29 spring forward in Lisbon at 01:00 UTC (00:30 UTC = 00:30 local, WET)
        (datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc), True),
        # 06:30 UTC = 07:30 WEST
        (datetime(2026, 3, 29, 6, 30, tzinfo=timezone.utc), True),
        # 07:30 UTC = 08:30 WEST: window over
        (datetime(2026, 3, 29, 7, 30, tzinfo=timezone.utc), False),
        # 2026-10-25 fall back at 01:00 UTC; 23:30 UTC on 24th = 00:30 WEST
        (datetime(2026, 10, 24, 23, 30, tzinfo=timezone.utc), True),
        # 07:30 UTC on the 25th = 07:30 WET
        (datetime(2026, 10, 25, 7, 30, tzinfo=timezone.utc), True),
        (datetime(2026, 10, 25, 8, 30, tzinfo=timezone.utc), False),
    ],
)
def test_lisbon_dst(now, expected):
    s = _setting(time(23), time(8), tz="Europe/Lisbon")
    assert is_active(s, now) is expected


def test_non_utc_zone_offset():
    s = _setting(time(23), time(8), tz="America/New_York")
    # 03:00 UTC in June = 23:00 EDT
    assert is_active(s, _utc(3))
    # 12:00 UTC = 08:00 EDT: ended
    assert not is_active(s, _utc(12))


async def test_store_get_maps_row():
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        return_value={
            "quiet_hours_enabled": True,
            "quiet_start": time(23),
            "quiet_end": time(8),
            "timezone": "Europe/Lisbon",
            "updated_at": _utc(1),
        }
    )
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    got = await InterruptionSettingsStore(pool).get()
    assert got.enabled and got.start == time(23) and got.timezone == "Europe/Lisbon"


async def test_store_get_without_row_is_disabled():
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    got = await InterruptionSettingsStore(pool).get()
    assert got == QuietHoursSetting(False, None, None, None, None)


async def test_store_upsert_uses_on_conflict():
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        return_value={
            "quiet_hours_enabled": True,
            "quiet_start": time(23),
            "quiet_end": time(8),
            "timezone": "UTC",
            "updated_at": _utc(1),
        }
    )
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    await InterruptionSettingsStore(pool).upsert(True, time(23), time(8), "UTC")
    sql = conn.fetchrow.call_args.args[0]
    assert "ON CONFLICT (id) DO UPDATE" in sql


async def test_store_get_error_propagates():
    pool = MagicMock()
    pool.acquire.side_effect = RuntimeError("down")
    with pytest.raises(RuntimeError):
        await InterruptionSettingsStore(pool).get()
