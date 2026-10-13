from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from ze_proactive import catchup
from ze_proactive.catchup import missed_fire_time
from ze_proactive.errors import CatchUpError

UTC = timezone.utc


def _dt(d, h, m=0):
    return datetime(2026, 6, d, h, m, tzinfo=UTC)


def test_daily_missed_today():
    assert missed_fire_time("0 8 * * *", _dt(14, 8), _dt(15, 10), UTC) == _dt(15, 8)


def test_daily_not_yet_due_returns_none():
    assert missed_fire_time("0 8 * * *", _dt(14, 8), _dt(15, 7), UTC) is None


def test_three_days_down_returns_only_latest():
    assert missed_fire_time("0 8 * * *", _dt(11, 8), _dt(15, 10), UTC) == _dt(15, 8)


def test_last_run_exactly_on_fire_time_is_not_missed():
    assert missed_fire_time("0 8 * * *", _dt(15, 8), _dt(15, 8, 30), UTC) is None


def test_five_minute_job_a_week_down_returns_latest_tick():
    got = missed_fire_time("*/5 * * * *", _dt(8, 0), _dt(15, 0, 3), UTC)
    assert got == _dt(15, 0, 0)


def test_iteration_cap_returns_last_computed(monkeypatch):
    monkeypatch.setattr(catchup, "_MAX_STEPS", 3)
    got = missed_fire_time("*/5 * * * *", _dt(8, 0), _dt(15, 0, 3), UTC)
    assert got == _dt(8, 0, 15)


def test_respects_timezone():
    lisbon = ZoneInfo("Europe/Lisbon")
    # 08:00 Lisbon (WEST) is 07:00 UTC in June.
    got = missed_fire_time("0 8 * * *", _dt(14, 9), _dt(15, 8), lisbon)
    assert got == datetime(2026, 6, 15, 7, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "last,now",
    [(datetime(2026, 6, 14, 8), _dt(15, 9)), (_dt(14, 8), datetime(2026, 6, 15, 9))],
)
def test_naive_datetime_raises(last, now):
    with pytest.raises(CatchUpError):
        missed_fire_time("0 8 * * *", last, now, UTC)
