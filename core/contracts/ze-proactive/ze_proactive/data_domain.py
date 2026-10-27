from __future__ import annotations

import asyncpg

from ze_data.domain import DataDomain
from ze_data.portability.assembler import bulk_insert


def _table_domain(pool: asyncpg.Pool, name: str, table: str) -> DataDomain:
    async def _export(p) -> list[dict]:
        async with pool.acquire() as conn:
            rows = await conn.fetch(f"SELECT * FROM {table}")
            return [dict(r) for r in rows]

    async def _delete(p) -> None:
        async with pool.acquire() as conn:
            await conn.execute(f"DELETE FROM {table}")

    async def _import(conn, rows: list[dict]) -> int:
        return await bulk_insert(conn, table, rows)

    async def _count(p) -> int:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(f"SELECT COUNT(*) AS n FROM {table}")
            return row["n"]

    async def _size(p) -> int:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT pg_total_relation_size($1::regclass) AS n", table
            )
            return row["n"]

    return DataDomain(
        name,
        _export,
        _delete,
        delete_order=10,
        importer=_import,
        count=_count,
        size_bytes=_size,
    )


def proactive_data_domains(pool: asyncpg.Pool) -> list[DataDomain]:
    """User data this package owns: quiet-hours settings (deleting turns quiet
    hours off) and the governor's push claims (`push_log`)."""
    return [
        _table_domain(pool, "proactive.interruption_settings", "interruption_settings"),
        _table_domain(pool, "proactive.log", "push_log"),
    ]
