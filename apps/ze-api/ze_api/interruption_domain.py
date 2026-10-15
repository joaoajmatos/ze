from __future__ import annotations

import asyncpg

from ze_data.domain import DataDomain
from ze_data.portability.assembler import bulk_insert

_TABLE = "interruption_settings"


def interruption_data_domains(pool: asyncpg.Pool) -> list[DataDomain]:
    """Quiet-hours settings are user data: exported, imported, and deleted (deleting turns quiet hours off)."""

    async def _export(p) -> list[dict]:
        async with pool.acquire() as conn:
            rows = await conn.fetch(f"SELECT * FROM {_TABLE}")
            return [dict(r) for r in rows]

    async def _delete(p) -> None:
        async with pool.acquire() as conn:
            await conn.execute(f"DELETE FROM {_TABLE}")

    async def _import(conn, rows: list[dict]) -> int:
        return await bulk_insert(conn, _TABLE, rows)

    async def _count(p) -> int:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(f"SELECT COUNT(*) AS n FROM {_TABLE}")
            return row["n"]

    async def _size(p) -> int:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT pg_total_relation_size($1::regclass) AS n", _TABLE
            )
            return row["n"]

    return [
        DataDomain(
            "proactive.interruption_settings",
            _export,
            _delete,
            delete_order=10,
            importer=_import,
            count=_count,
            size_bytes=_size,
        )
    ]
