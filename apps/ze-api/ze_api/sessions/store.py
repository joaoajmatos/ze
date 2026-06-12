from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

import asyncpg

from ze_api.sessions.types import Session


class SessionStore(Protocol):
    async def upsert(
        self,
        session_id: str,
        *,
        title: str | None = None,
        preview: str | None = None,
    ) -> None: ...

    async def list_all(self, limit: int = 50) -> list[Session]: ...

    async def get(self, session_id: str) -> Session | None: ...


class PostgresSessionStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def upsert(
        self,
        session_id: str,
        *,
        title: str | None = None,
        preview: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sessions (id, title, preview, created_at, last_active_at)
                VALUES ($1, $2, $3, $4, $4)
                ON CONFLICT (id) DO UPDATE SET
                    title = COALESCE(sessions.title, EXCLUDED.title),
                    preview = COALESCE(EXCLUDED.preview, sessions.preview),
                    last_active_at = EXCLUDED.last_active_at
                """,
                session_id,
                title,
                preview,
                now,
            )

    async def list_all(self, limit: int = 50) -> list[Session]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, title, preview, created_at, last_active_at
                FROM sessions
                ORDER BY last_active_at DESC
                LIMIT $1
                """,
                limit,
            )
        return [_row_to_session(r) for r in rows]

    async def get(self, session_id: str) -> Session | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, title, preview, created_at, last_active_at
                FROM sessions
                WHERE id = $1
                """,
                session_id,
            )
        return _row_to_session(row) if row else None


def _row_to_session(row: asyncpg.Record) -> Session:
    return Session(
        id=row["id"],
        title=row["title"],
        preview=row["preview"],
        created_at=row["created_at"],
        last_active_at=row["last_active_at"],
    )
