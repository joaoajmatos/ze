from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from tests.pg._builders import make_episode
from ze_personal.contacts.consolidator import ContactsConsolidator
from ze_personal.contacts.types import Person

pytestmark = pytest.mark.pg


def _consolidator(pool, client):
    store = AsyncMock()
    store.get_by_name = AsyncMock(return_value=[])
    store.upsert = AsyncMock(return_value=Person(name="Rita Gomes", id=uuid4()))
    store.add_source = AsyncMock()
    store.memory_store = None
    return ContactsConsolidator(pool=pool, person_store=store, openrouter_client=client)


async def test_consolidator_reads_turn_episodes_once_past_the_watermark(pg_pool):
    async with pg_pool.acquire() as conn:
        await conn.execute("TRUNCATE contacts_episode_watermark")
    first = await make_episode(pg_pool, prompt="Lunch with Rita Gomes from Acme")
    await make_episode(pg_pool, agent="consolidator", prompt="archive")
    client = AsyncMock()
    client.complete = AsyncMock(return_value='{"people": [], "projects": [], "relationships": []}')
    consolidator = _consolidator(pg_pool, client)

    report = await consolidator.run()

    assert report.episodes_scanned == 1
    assert "Rita Gomes" in client.complete.call_args.kwargs["messages"][0]["content"]
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT last_episode_id FROM contacts_episode_watermark") == first

    assert (await consolidator.run()).episodes_scanned == 0

    second = await make_episode(pg_pool, prompt="Call with Tiago Lopes")
    report = await consolidator.run()

    assert report.episodes_scanned == 1
    assert "Tiago Lopes" in client.complete.call_args.kwargs["messages"][0]["content"]
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT last_episode_id FROM contacts_episode_watermark") == second
