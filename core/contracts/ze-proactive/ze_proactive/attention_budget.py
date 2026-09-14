from __future__ import annotations

from typing import Any, Final, Literal
from uuid import UUID

from ze_logging import get_logger

log = get_logger(__name__)

ATTENTION_PUSH_EVENT_KEY: Final[str] = "attention_push"

SourceKind = Literal["loop", "goal", "hypothesis"]


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
        count = await push_log.count_sent_within_hours(
            ATTENTION_PUSH_EVENT_KEY, window_hours
        )
        return count < max_per_day
    except Exception as exc:
        log.warning("attention_budget_check_failed", error=str(exc))
        return True


async def try_claim_shared(
    push_log: Any,
    source_kind: SourceKind,
    source_id: UUID,
    max_per_day: int,
    *,
    payload: str | None = None,
    window_hours: float = 24.0,
) -> bool:
    """True = claim won, caller may send. False = budget exhausted or another
    caller already claimed this exact (source_kind, source_id) — generalizes the
    claim-then-notify pattern `LoopSurfacer` already used to one shared key
    (FR-008)."""
    if not await within_budget(push_log, max_per_day, window_hours=window_hours):
        return False
    return await push_log.try_claim(
        ATTENTION_PUSH_EVENT_KEY,
        idempotency_key=f"{source_kind}:{source_id}",
        payload=payload,
    )


async def release_shared(
    push_log: Any,
    source_kind: SourceKind,
    source_id: UUID,
) -> None:
    """Roll back a claim whose notification was never delivered, so a failed
    send doesn't permanently burn that day's budget slot."""
    await push_log.release_claim(
        ATTENTION_PUSH_EVENT_KEY, idempotency_key=f"{source_kind}:{source_id}"
    )
