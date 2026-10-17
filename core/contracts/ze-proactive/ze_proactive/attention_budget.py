from __future__ import annotations

from typing import Any, Final

from ze_logging import get_logger
from ze_proactive.types import BudgetStatus

log = get_logger(__name__)

ATTENTION_PUSH_EVENT_KEY: Final[str] = "attention_push"


async def budget_status(
    push_log: Any,
    max_per_day: int,
    *,
    window_hours: float = 24.0,
) -> BudgetStatus:
    """The one count of the rolling attention window. Raises on store failure."""
    stamps = await push_log.window_sent_at(ATTENTION_PUSH_EVENT_KEY, window_hours)
    return BudgetStatus(max_per_day, window_hours, tuple(stamps))


async def within_budget(
    push_log: Any,
    max_per_day: int,
    *,
    window_hours: float = 24.0,
) -> bool:
    """Moved from `ze_correlation.push` (FR-006) — the one shared budget check
    every mechanism now calls, keyed by `ATTENTION_PUSH_EVENT_KEY` instead of a
    per-mechanism event type."""
    try:
        status = await budget_status(push_log, max_per_day, window_hours=window_hours)
        return status.remaining > 0
    except Exception as exc:
        log.warning("attention_budget_check_failed", error=str(exc))
        return True


async def try_claim_shared(
    push_log: Any,
    budget_key: str,
    max_per_day: int,
    *,
    payload: str | None = None,
    window_hours: float = 24.0,
) -> bool:
    """True = claim won, caller may send. False = budget exhausted or another
    caller already claimed this exact `budget_key` — the claim-then-notify
    pattern, with one shared counter across every discretionary push."""
    if not await within_budget(push_log, max_per_day, window_hours=window_hours):
        return False
    return await push_log.try_claim(
        ATTENTION_PUSH_EVENT_KEY,
        idempotency_key=budget_key,
        payload=payload,
    )


async def release_shared(
    push_log: Any,
    budget_key: str,
) -> None:
    """Roll back a claim whose notification was never delivered, so a failed
    send doesn't permanently burn that day's budget slot."""
    await push_log.release_claim(ATTENTION_PUSH_EVENT_KEY, idempotency_key=budget_key)
