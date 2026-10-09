from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from ze_api.feedback_domain import feedback_data_domains
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


async def test_domain_exports_deletes_counts_feedback_records():
    pool, conn = _pool(rows=[{"id": 1, "kind": "thumbs_up"}])
    [domain] = feedback_data_domains(pool)
    assert domain.name == "feedback.records"
    assert await domain.export(pool) == [{"id": 1, "kind": "thumbs_up"}]
    assert "FROM feedback_records" in conn.fetch.call_args[0][0]
    await domain.delete(pool)
    assert conn.execute.call_args[0][0] == "DELETE FROM feedback_records"
    assert await domain.count(pool) == 3
    assert domain.importer is not None


def test_message_export_selects_supersession_columns():
    import inspect

    from ze_core import bootstrap

    src = inspect.getsource(bootstrap.engine_data_domains)
    assert "SELECT * FROM {tbl}" in src
    assert '_engine_domain("messages.store", "messages")' in src
