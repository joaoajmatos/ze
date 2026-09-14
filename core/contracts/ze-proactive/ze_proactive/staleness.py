from __future__ import annotations

from datetime import UTC, datetime, timedelta


def is_stale(timestamp: datetime, window_days: int, *, now: datetime | None = None) -> bool:
    cutoff = (now or datetime.now(UTC)) - timedelta(days=window_days)
    return timestamp <= cutoff
