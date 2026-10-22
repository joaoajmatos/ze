from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from ze_memory.migrations.versions import zm026_perception_fact_provenance as zm026

pytestmark = pytest.mark.pg

STAMP = datetime(2026, 9, 1, tzinfo=timezone.utc)


async def _insert(
    conn,
    *,
    provenance,
    claim_kind,
    dream_run_id=None,
    confidence=0.8,
    contradicted=False,
):
    fact_id = uuid4()
    await conn.execute(
        """
        INSERT INTO memory_facts (
            id, predicate, value, confidence, contradicted, provenance,
            claim_kind, corroborated, dream_run_id, created_at, updated_at
        ) VALUES ($1, 'p', 'v', $2, $3, $4, $5, false, $6, $7, $7)
        """,
        fact_id,
        confidence,
        contradicted,
        provenance,
        claim_kind,
        dream_run_id,
        STAMP - timedelta(days=60),
    )
    return fact_id


async def _snapshot(conn):
    rows = await conn.fetch(
        "SELECT id, provenance, claim_kind, confidence, contradicted, updated_at "
        "FROM memory_facts"
    )
    return {r["id"]: dict(r) for r in rows}


async def test_restamp_fixes_perception_facts_and_reports_damage(pg_pool):
    async with pg_pool.acquire() as conn:
        await conn.execute("TRUNCATE memory_facts CASCADE")
        a = await _insert(
            conn,
            provenance="synthesized",
            claim_kind="inference",
            confidence=0.2,
            contradicted=True,
        )
        b = await _insert(conn, provenance="synthesized", claim_kind="fact")
        c = await _insert(
            conn,
            provenance="synthesized",
            claim_kind="inference",
            dream_run_id=uuid4(),
        )
        d = await _insert(conn, provenance="prompt_supplied", claim_kind="fact")
        e = await _insert(conn, provenance="live_search", claim_kind="fact")
        before = await _snapshot(conn)

        counts = await conn.fetchrow(zm026.COUNT_SQL)
        assert counts["restamped"] == 2
        assert counts["decay_damaged"] == 1

        await conn.execute(zm026.REPAIR_SQL)
        after = await _snapshot(conn)

        for fact_id in (a, b):
            assert after[fact_id]["provenance"] == "prompt_supplied"
            assert after[fact_id]["claim_kind"] == "fact"
        assert after[a]["confidence"] == pytest.approx(0.2)
        assert after[a]["contradicted"] is True
        for fact_id in (c, d, e):
            assert after[fact_id] == before[fact_id]
        for fact_id in (a, b):
            assert after[fact_id]["updated_at"] == before[fact_id]["updated_at"]

        again = await conn.fetchrow(zm026.COUNT_SQL)
        assert again["restamped"] == 0
        await conn.execute(zm026.REPAIR_SQL)
        assert await _snapshot(conn) == after
