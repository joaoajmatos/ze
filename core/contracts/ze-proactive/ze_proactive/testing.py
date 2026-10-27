from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ze_proactive.push_log_store import ClaimResult
from ze_proactive.types import OncePer


@dataclass
class _Row:
    id: int
    event_type: str
    claim_key: str
    discretionary: bool
    payload: str | None
    sent_at: datetime


class InMemoryPushLog:
    """The private claim-store contract held in memory, for tests that want a
    real `ProactiveNotifier`. `clock` moves time without sleeping.

    It takes no key lock, so it does not model two claims racing; the real
    store's concurrency is covered by the pg test in `test_push_claims_pg.py`."""

    def __init__(
        self, clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    ) -> None:
        self._clock = clock
        self._rows: list[_Row] = []
        self._next_id = 1

    @property
    def rows(self) -> list[_Row]:
        return list(self._rows)

    def _cooling(self, once_per: OncePer) -> bool:
        floor = None if once_per.within is None else self._clock() - once_per.within
        return any(
            r.claim_key == once_per.key and (floor is None or r.sent_at > floor)
            for r in self._rows
        )

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
        if self._cooling(once_per):
            return ClaimResult("cooling")
        if discretionary and (
            len(await self.window_sent_at(budget_window_hours)) >= max_discretionary
        ):
            return ClaimResult("over_budget")
        row = _Row(
            self._next_id,
            event_type,
            once_per.key,
            discretionary,
            payload,
            self._clock(),
        )
        self._next_id += 1
        self._rows.append(row)
        return ClaimResult("won", row.id)

    async def release(self, claim_id: int) -> None:
        self._rows = [r for r in self._rows if r.id != claim_id]

    async def is_cooling(self, once_per: OncePer) -> bool:
        return self._cooling(once_per)

    async def window_sent_at(self, hours: float) -> list[datetime]:
        floor = self._clock() - timedelta(hours=hours)
        return sorted(
            r.sent_at for r in self._rows if r.discretionary and r.sent_at > floor
        )

    async def recent_discretionary_payloads(self, hours: float) -> list[str]:
        floor = self._clock() - timedelta(hours=hours)
        recent = sorted(
            (r for r in self._rows if r.discretionary and r.sent_at > floor),
            key=lambda r: r.sent_at,
            reverse=True,
        )
        return [r.payload for r in recent if r.payload is not None]
