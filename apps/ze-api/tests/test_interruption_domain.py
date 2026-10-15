from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from ze_api.interruption_domain import interruption_data_domains
from ze_data.portability.assembler import bulk_insert  # noqa: F401


def _pool(rows=None):
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows or [])
    conn.fetchrow = AsyncMock(return_value={"n": 3})
    conn.execute = AsyncMock()

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    return pool, conn


async def test_domain_exports_deletes_counts_interruption_settings():
    pool, conn = _pool(rows=[{"id": 1, "kind": "quiet"}])
    [domain] = interruption_data_domains(pool)
    assert domain.name == "proactive.interruption_settings"
    assert await domain.export(pool) == [{"id": 1, "kind": "quiet"}]
    assert "FROM interruption_settings" in conn.fetch.call_args[0][0]
    await domain.delete(pool)
    assert conn.execute.call_args[0][0] == "DELETE FROM interruption_settings"
    assert await domain.count(pool) == 3
    assert domain.importer is not None
