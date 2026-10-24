from uuid import uuid4

import pytest
from ze_memory.consolidation_store import PostgresConsolidationStore

pytestmark = pytest.mark.pg


async def test_fetch_active_facts_returns_claim_columns(pg_pool):
    run_id = uuid4()
    async with pg_pool.acquire() as conn:
        await conn.execute("TRUNCATE memory_facts CASCADE")
        await conn.execute(
            """
            INSERT INTO memory_facts (
                predicate, value, provenance, claim_kind, dream_run_id
            ) VALUES ('p', 'v', 'synthesized', 'inference', $1)
            """,
            run_id,
        )
    rows = await PostgresConsolidationStore(pg_pool).fetch_active_facts()
    assert len(rows) == 1
    assert rows[0]["provenance"] == "synthesized"
    assert rows[0]["claim_kind"] == "inference"
    assert rows[0]["dream_run_id"] == run_id


async def test_insert_merged_fact_keeps_the_inputs_claim(pg_pool):
    async with pg_pool.acquire() as conn:
        await conn.execute("TRUNCATE memory_facts CASCADE")
    await PostgresConsolidationStore(pg_pool).insert_merged_fact(
        "diet",
        "likes and enjoys coffee",
        0.9,
        [0.1] * 768,
        provenance="prompt_supplied",
        claim_kind="fact",
    )
    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT provenance, claim_kind, agent, dream_run_id FROM memory_facts"
        )
    assert row["provenance"] == "prompt_supplied"
    assert row["claim_kind"] == "fact"
    assert row["agent"] == "consolidation"
    assert row["dream_run_id"] is None
