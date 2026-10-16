from __future__ import annotations

import json
from datetime import datetime
from typing import Protocol

import asyncpg

from ze_automation.holds.types import HeldWrite, HeldWriteStatus


class HeldWriteStore(Protocol):
    async def create(self, hold: HeldWrite) -> None: ...

    async def get(self, request_id: str) -> HeldWrite | None: ...

    async def list(self, status: HeldWriteStatus) -> list[HeldWrite]: ...

    async def decide(self, request_id: str, status: HeldWriteStatus) -> bool:
        """Move an open hold to a terminal status. False when it was not open."""
        ...

    async def list_expired(self, now: datetime) -> list[HeldWrite]: ...


def _jsonb(value: object) -> object:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _from_row(row: asyncpg.Record) -> HeldWrite:
    return HeldWrite(
        request_id=row["request_id"],
        source=row["source"],
        owner_ref=row["owner_ref"],
        items=_jsonb(row["items"]),
        payload=_jsonb(row["payload"]),
        expires_at=row["expires_at"],
        status=HeldWriteStatus(row["status"]),
        created_at=row["created_at"],
        decided_at=row["decided_at"],
    )


class PostgresHeldWriteStore:
    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self._pool = db_pool

    async def create(self, hold: HeldWrite) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO held_writes
                    (request_id, source, owner_ref, items, payload, status, expires_at)
                VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, $7)
                """,
                hold.request_id,
                hold.source,
                hold.owner_ref,
                json.dumps(hold.items),
                json.dumps(hold.payload),
                str(hold.status),
                hold.expires_at,
            )

    async def get(self, request_id: str) -> HeldWrite | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM held_writes WHERE request_id = $1", request_id
            )
        return _from_row(row) if row else None

    async def list(self, status: HeldWriteStatus) -> list[HeldWrite]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM held_writes
                WHERE status = $1
                ORDER BY created_at DESC
                """,
                str(status),
            )
        return [_from_row(row) for row in rows]

    async def decide(self, request_id: str, status: HeldWriteStatus) -> bool:
        async with self._pool.acquire() as conn:
            decided = await conn.fetchval(
                """
                UPDATE held_writes
                SET status = $2, decided_at = now()
                WHERE request_id = $1 AND status = 'open'
                RETURNING request_id
                """,
                request_id,
                str(status),
            )
        return decided is not None

    async def list_expired(self, now: datetime) -> list[HeldWrite]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM held_writes
                WHERE status = 'open' AND expires_at <= $1
                ORDER BY expires_at
                """,
                now,
            )
        return [_from_row(row) for row in rows]
