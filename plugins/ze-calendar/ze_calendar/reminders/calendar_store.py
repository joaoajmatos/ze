from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from ze_logging import get_logger

log = get_logger(__name__)


@dataclass
class CalendarReminder:
    id: UUID
    event_id: str
    event_title: str
    fire_at: datetime
    label: str
    sent: bool
    assessed_at: datetime


class CalendarReminderStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_unsent(
        self, *, include_overdue: bool = False
    ) -> list[CalendarReminder]:
        """Unsent reminders ordered by fire time.

        Defaults to upcoming reminders only (what ``CalendarSignalSource``
        wants). Pass ``include_overdue=True`` so ``replay_unsent`` also sees
        reminders whose fire time passed while the host was down (FR-025).
        """
        condition = "" if include_overdue else " AND fire_at > NOW()"
        query = (
            "SELECT id, event_id, event_title, fire_at, label, sent, assessed_at "
            f"FROM calendar_reminders WHERE sent = false{condition} ORDER BY fire_at"
        )
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)
        return [_to_reminder(r) for r in rows]

    async def list_for_event(self, event_id: str) -> list[CalendarReminder]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, event_id, event_title, fire_at, label, sent, assessed_at "
                "FROM calendar_reminders WHERE event_id = $1",
                event_id,
            )
        return [_to_reminder(r) for r in rows]

    async def create(
        self,
        event_id: str,
        event_title: str,
        fire_at: datetime,
        label: str,
    ) -> UUID:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO calendar_reminders (event_id, event_title, fire_at, label)
                VALUES ($1, $2, $3, $4) RETURNING id
                """,
                event_id,
                event_title,
                fire_at,
                label,
            )
        return row["id"]

    async def mark_sent(self, reminder_id: UUID) -> str | None:
        """Atomically mark sent. Returns the label if claimed, None if already sent."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE calendar_reminders SET sent = true, sent_at = NOW() "
                "WHERE id = $1 AND sent = false RETURNING label",
                reminder_id,
            )
        return row["label"] if row else None

    async def mark_unsent(self, reminder_id: UUID) -> None:
        """Undo `mark_sent` after a failed push, so the next startup replay sends it."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE calendar_reminders SET sent = false, sent_at = NULL "
                "WHERE id = $1",
                reminder_id,
            )

    async def delete_unsent_for_event(self, event_id: str) -> list[UUID]:
        """Delete unsent reminders for an event (e.g. when event is updated). Returns deleted IDs."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "DELETE FROM calendar_reminders WHERE event_id = $1 AND sent = false RETURNING id",
                event_id,
            )
        return [r["id"] for r in rows]


def _to_reminder(row) -> CalendarReminder:
    return CalendarReminder(
        id=row["id"],
        event_id=row["event_id"],
        event_title=row["event_title"],
        fire_at=row["fire_at"],
        label=row["label"],
        sent=row["sent"],
        assessed_at=row["assessed_at"],
    )
