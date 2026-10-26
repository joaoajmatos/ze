from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import asyncpg

from ze_logging import get_logger
from ze_proactive.types import OncePer

log = get_logger(__name__)


@dataclass(frozen=True)
class ClaimResult:
    status: Literal["won", "cooling", "over_budget"]
    claim_id: int | None = None  # set only when won


_KEY_LOCK = "SELECT pg_advisory_xact_lock(hashtext('push_log:key:' || $1))"
_BUDGET_LOCK = "SELECT pg_advisory_xact_lock(hashtext('push_log:budget'))"
_COOLING = (
    "SELECT 1 FROM push_log WHERE claim_key = $1 "
    "AND ($2::interval IS NULL OR sent_at > now() - $2::interval) LIMIT 1"
)
_BUDGET_COUNT = (
    "SELECT count(*) FROM push_log WHERE discretionary "
    "AND sent_at > now() - ($1 * INTERVAL '1 hour')"
)
_INSERT = (
    "INSERT INTO push_log (event_type, claim_key, discretionary, payload) "
    "VALUES ($1, $2, $3, $4) RETURNING id"
)


class PushLogStore:
    """The governor's claim table. Private to ze-proactive: only
    `ProactiveNotifier` takes and releases claims."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def claim(
        self,
        *,
        event_type: str,
        once_per: OncePer,
        discretionary: bool,
        max_discretionary: int,
        payload: str | None,
        budget_window_hours: float = 24.0,
    ) -> ClaimResult:
        """One transaction: key lock, then (discretionary) budget lock, cooldown
        check, budget count, insert. The key lock makes "once per window" exact;
        the budget lock makes the daily cap exact. Both locks are always taken
        in that order, so two claims never wait on each other in a cycle."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(_KEY_LOCK, once_per.key)
                if discretionary:
                    await conn.execute(_BUDGET_LOCK)
                if await conn.fetchval(_COOLING, once_per.key, once_per.within):
                    return ClaimResult("cooling")
                if discretionary:
                    used = await conn.fetchval(_BUDGET_COUNT, budget_window_hours)
                    if used >= max_discretionary:
                        return ClaimResult("over_budget")
                claim_id = await conn.fetchval(
                    _INSERT, event_type, once_per.key, discretionary, payload
                )
        return ClaimResult("won", claim_id)

    async def release(self, claim_id: int) -> None:
        """Roll back a claim whose push was never delivered."""
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM push_log WHERE id = $1", claim_id)

    async def is_cooling(self, once_per: OncePer) -> bool:
        async with self._pool.acquire() as conn:
            row = await conn.fetchval(_COOLING, once_per.key, once_per.within)
        return row is not None

    async def window_sent_at(self, hours: float) -> list[datetime]:
        """Send times of the discretionary claims inside the window, ascending."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT sent_at FROM push_log WHERE discretionary "
                "AND sent_at > now() - ($1 * INTERVAL '1 hour') "
                "ORDER BY sent_at ASC",
                hours,
            )
        return [r["sent_at"] for r in rows]

    async def recent_discretionary_payloads(self, hours: float) -> list[str]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT payload FROM push_log WHERE discretionary "
                "AND payload IS NOT NULL "
                "AND sent_at > now() - ($1 * INTERVAL '1 hour') "
                "ORDER BY sent_at DESC",
                hours,
            )
        return [r["payload"] for r in rows]
