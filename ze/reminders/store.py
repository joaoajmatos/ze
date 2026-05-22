from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from ze.logging import get_logger

log = get_logger(__name__)


@dataclass
class Reminder:
    id: UUID
    label: str
    fire_at: datetime
    created_at: datetime
    sent: bool
    sent_at: datetime | None


class ReminderStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, label: str, fire_at: datetime) -> UUID:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO user_reminders (label, fire_at) VALUES ($1, $2) RETURNING id",
                label, fire_at,
            )
        return row["id"]

    async def list_pending(self) -> list[Reminder]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, label, fire_at, created_at, sent, sent_at "
                "FROM user_reminders WHERE sent = false AND fire_at > NOW() ORDER BY fire_at"
            )
        return [_to_reminder(r) for r in rows]

    async def get(self, reminder_id: UUID) -> Reminder | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, label, fire_at, created_at, sent, sent_at "
                "FROM user_reminders WHERE id = $1",
                reminder_id,
            )
        return _to_reminder(row) if row else None

    async def delete(self, reminder_id: UUID) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM user_reminders WHERE id = $1", reminder_id)

    async def mark_sent(self, reminder_id: UUID) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_reminders SET sent = true, sent_at = NOW() WHERE id = $1",
                reminder_id,
            )


async def fire_reminder(store: ReminderStore, notifier, reminder_id: UUID) -> None:
    """Push the reminder and mark it sent. Safe to call redundantly — checks sent first."""
    reminder = await store.get(reminder_id)
    if reminder is None:
        log.warning("reminder_missing", id=str(reminder_id))
        return
    if reminder.sent:
        return
    await notifier.push(f"⏰ {reminder.label}")
    await store.mark_sent(reminder_id)
    log.info("reminder_fired", id=str(reminder_id), label=reminder.label)


def _to_reminder(row) -> Reminder:
    return Reminder(
        id=row["id"],
        label=row["label"],
        fire_at=row["fire_at"],
        created_at=row["created_at"],
        sent=row["sent"],
        sent_at=row["sent_at"],
    )
