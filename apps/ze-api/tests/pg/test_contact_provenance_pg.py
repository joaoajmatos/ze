from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from ze_personal.contacts.consolidator import ContactsConsolidator
from ze_personal.contacts.store import PersonStore
from ze_personal.contacts.types import ContactProposal
from ze_api.wiring.db import _init_conn
from ze_prospecting.agents.tools import add_prospect

pytestmark = pytest.mark.pg


@pytest_asyncio.fixture
async def contacts_pool(pg_dsn):
    # PersonStore writes contact_info as jsonb, so the pool needs the app's codecs.
    pool = await asyncpg.create_pool(pg_dsn, min_size=1, max_size=2, init=_init_conn)
    yield pool
    await pool.close()


async def _truncate(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE contacts CASCADE")


async def _stored(pool, name: str) -> tuple[str, list[tuple[str, str]]]:
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "SELECT id, provenance FROM contacts WHERE name = $1", name
        )
        sources = await conn.fetch(
            "SELECT source_type, provenance FROM contact_sources WHERE contact_id = $1",
            contact["id"],
        )
    return contact["provenance"], [(r["source_type"], r["provenance"]) for r in sources]


@pytest.mark.parametrize("source_type", ["email", "calendar", "conversation"])
async def test_consolidator_stores_prompt_supplied_for_the_users_own_sources(
    contacts_pool, source_type
):
    await _truncate(contacts_pool)
    consolidator = ContactsConsolidator(
        pool=contacts_pool, person_store=PersonStore(contacts_pool), openrouter_client=AsyncMock()
    )
    name = f"Rita {source_type}"

    created = await consolidator._store_candidate(
        ContactProposal(name=name, source_type=source_type, confidence=0.7)
    )

    assert created is True
    assert await _stored(contacts_pool, name) == (
        "prompt_supplied",
        [(source_type, "prompt_supplied")],
    )


async def test_prospecting_stores_a_research_source_as_live_search(contacts_pool):
    await _truncate(contacts_pool)
    campaign_store = AsyncMock()
    campaign_store.add_outreach = AsyncMock(return_value=uuid4())

    await add_prospect(
        name="Maria Santos",
        company="AirCharter PT",
        role="CEO",
        relationship="charter operator",
        contact_info={"email": "maria@aircharter.pt"},
        source_url="https://aircharter.pt/about",
        enrichment_notes="email found on website",
        campaign_id=str(uuid4()),
        channel="email",
        person_store=PersonStore(contacts_pool),
        campaign_store=campaign_store,
    )

    assert await _stored(contacts_pool, "Maria Santos") == (
        "live_search",
        [("research", "live_search")],
    )


async def _seed_contact(conn, name: str, sources: list[tuple[str, str]]) -> None:
    contact_id = uuid4()
    await conn.execute(
        "INSERT INTO contacts (id, name, claim_kind, provenance) "
        "VALUES ($1, $2, 'identity', 'synthesized')",
        contact_id,
        name,
    )
    for offset, (source_type, provenance) in enumerate(sources):
        await conn.execute(
            "INSERT INTO contact_sources "
            "(contact_id, source_type, weight, claim_kind, provenance, created_at) "
            "VALUES ($1, $2, 0.5, 'identity', $3, now() + make_interval(secs => $4))",
            contact_id,
            source_type,
            provenance,
            float(offset),
        )


async def test_zc041_restamps_sources_then_contacts_and_is_idempotent(contacts_pool):
    from ze_personal.migrations.versions import zc041_contact_source_provenance as zc041

    await _truncate(contacts_pool)
    async with contacts_pool.acquire() as conn:
        await _seed_contact(
            conn,
            "Via email",
            [("email", "synthesized"), ("research", "synthesized")],
        )
        await _seed_contact(conn, "Via research", [("research", "synthesized")])
        await _seed_contact(conn, "No sources", [])
        first = await conn.fetchrow(zc041.REPAIR_SQL)

    assert (first["sources"], first["contacts"]) == (3, 2)
    assert await _stored(contacts_pool, "Via email") == (
        "prompt_supplied",
        [("email", "prompt_supplied"), ("research", "live_search")],
    )
    assert await _stored(contacts_pool, "Via research") == (
        "live_search",
        [("research", "live_search")],
    )
    assert await _stored(contacts_pool, "No sources") == ("synthesized", [])

    async with contacts_pool.acquire() as conn:
        second = await conn.fetchrow(zc041.REPAIR_SQL)
    assert (second["sources"], second["contacts"]) == (0, 0)
