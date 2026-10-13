from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_plugin.contribution import EvidenceRef

from ze_worldstate.rest import _fetch_evidence_summaries


async def test_episode_summary_uses_the_messenger_body_branch():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"s": "Passport renewal Please send the form by Friday"})

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    episode_id = uuid4()
    loop_store = AsyncMock()
    loop_store.list_evidence = AsyncMock(return_value=[EvidenceRef(kind="episode", id=episode_id)])

    result = await _fetch_evidence_summaries(pool, loop_store, uuid4())

    sql = conn.fetchrow.await_args.args[0]
    assert "agent = 'messenger'" in sql
    assert "left(response, 500)" in sql
    assert result[0]["summary"] == "Passport renewal Please send the form by Friday"
