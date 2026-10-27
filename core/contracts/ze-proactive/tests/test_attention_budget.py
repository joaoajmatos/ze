from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from ze_proactive.attention_budget import budget_status

NOW = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)


def _push_log(hours_ago: list[float]) -> MagicMock:
    push_log = MagicMock()
    push_log.window_sent_at = AsyncMock(
        return_value=sorted(NOW - timedelta(hours=h) for h in hours_ago)
    )
    return push_log


async def test_budget_status_counts_the_window_and_reports_remaining():
    push_log = _push_log([1, 2])
    status = await budget_status(push_log, 5)
    push_log.window_sent_at.assert_awaited_once_with(24.0)
    assert (status.used, status.remaining, status.max_per_day) == (2, 3, 5)


async def test_next_slot_opens_when_the_oldest_claim_leaves_the_window():
    status = await budget_status(_push_log([20, 10, 5]), 3)
    assert status.remaining == 0
    assert status.next_slot_at == NOW - timedelta(hours=20) + timedelta(hours=24)


async def test_budget_status_raises_on_store_failure():
    push_log = MagicMock()
    push_log.window_sent_at = AsyncMock(side_effect=RuntimeError("db down"))
    try:
        await budget_status(push_log, 3)
    except RuntimeError:
        return
    raise AssertionError("budget_status must raise")
