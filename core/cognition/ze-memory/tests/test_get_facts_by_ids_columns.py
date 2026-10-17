from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_memory.retriever import PostgresMemoryStore


async def test_get_facts_by_ids_selects_what_fact_rows_need():
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    retriever = PostgresMemoryStore.__new__(PostgresMemoryStore)
    retriever._pool = pool
    await retriever.get_facts_by_ids([uuid4()])
    sql = conn.fetch.await_args.args[0]
    for column in ("provenance", "claim_kind", "created_at"):
        assert column in sql
