from __future__ import annotations

from typing import Any

from ze_proactive.types import BudgetStatus


async def budget_status(
    push_log: Any,
    max_per_day: int,
    *,
    window_hours: float = 24.0,
) -> BudgetStatus:
    """The one count of the rolling attention window. Raises on store failure."""
    stamps = await push_log.window_sent_at(window_hours)
    return BudgetStatus(max_per_day, window_hours, tuple(stamps))
