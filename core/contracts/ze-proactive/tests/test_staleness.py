from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ze_proactive.staleness import is_stale

_NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)


def test_is_stale_true_when_older_than_window():
    timestamp = _NOW - timedelta(days=15)
    assert is_stale(timestamp, window_days=14, now=_NOW) is True


def test_is_stale_false_when_within_window():
    timestamp = _NOW - timedelta(days=13)
    assert is_stale(timestamp, window_days=14, now=_NOW) is False


def test_is_stale_true_exactly_at_cutoff():
    timestamp = _NOW - timedelta(days=14)
    assert is_stale(timestamp, window_days=14, now=_NOW) is True


def test_is_stale_honors_now_override():
    timestamp = datetime(2020, 1, 1, tzinfo=UTC)
    assert is_stale(timestamp, window_days=14, now=_NOW) is True
    assert is_stale(timestamp, window_days=14, now=timestamp) is False
