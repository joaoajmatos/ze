from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from ze_memory.dream.promoter import DreamPromoter

pytestmark = pytest.mark.pg

NOW = datetime.now(timezone.utc)


def _promoter(pool, artifacts=()):
    store = MagicMock()
    store.get_pending_artifacts_for_run = AsyncMock(return_value=list(artifacts))
    store.update_artifact_status = AsyncMock()
    store.mark_artifact_promoted = AsyncMock()
    return DreamPromoter(pool, dream_store=store), store


async def _insert_fact(
    pool,
    *,
    dream_run_id=None,
    confidence=0.8,
    reviewed=True,
    valid_until=None,
    agent="companion",
):
    fact_id = uuid4()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO memory_facts (
                id, predicate, value, confidence, reviewed, provenance,
                claim_kind, corroborated, contradicted, valid_until,
                dream_run_id, agent, created_at
            ) VALUES (
                $1, 'p', 'v', $2, $3, 'synthesized',
                'fact', false, false, $4, $5, $6, $7
            )
            """,
            fact_id,
            confidence,
            reviewed,
            valid_until,
            dream_run_id,
            agent,
            NOW - timedelta(days=60),
        )
    return fact_id


async def _row(pool, fact_id):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT confidence, reviewed, contradicted FROM memory_facts WHERE id = $1",
            fact_id,
        )


async def test_decay_leaves_synthesized_fact_without_dream_run_alone(pg_pool):
    fact_id = await _insert_fact(pg_pool)
    promoter, _ = _promoter(pg_pool)
    for _ in range(10):
        await promoter.run_morning_integration(uuid4())
    row = await _row(pg_pool, fact_id)
    assert row["confidence"] == pytest.approx(0.8)
    assert row["reviewed"] is True
    assert row["contradicted"] is False


async def test_decay_steps_a_dream_insight_by_one_notch(pg_pool):
    fact_id = await _insert_fact(pg_pool, dream_run_id=uuid4())
    promoter, _ = _promoter(pg_pool)
    await promoter.run_morning_integration(uuid4())
    row = await _row(pg_pool, fact_id)
    assert row["confidence"] == pytest.approx(0.77)


async def test_expiry_contradicts_only_dream_insights(pg_pool):
    past = NOW - timedelta(days=1)
    perception = await _insert_fact(pg_pool, valid_until=past, confidence=0.8)
    insight = await _insert_fact(
        pg_pool, dream_run_id=uuid4(), valid_until=past, confidence=0.8
    )
    promoter, _ = _promoter(pg_pool)
    await promoter.run_morning_integration(uuid4())
    assert (await _row(pg_pool, perception))["contradicted"] is False
    assert (await _row(pg_pool, insight))["contradicted"] is True


async def test_promotion_inserts_an_insight_and_decay_still_runs(pg_pool):
    aged = await _insert_fact(pg_pool, dream_run_id=uuid4())
    artifact = {
        "id": uuid4(),
        "artifact_type": "synthesized_insight",
        "status": "pending",
        "content": "Ze noticed a pattern",
        "critic_a_verdict": "PASS",
        "critic_b_verdict": "PASS",
        "support_count": 10,
        "distinct_session_count": 10,
        "temporal_spread_days": 30,
        "user_asserted_source_count": 0,
        "source_fact_ids": [],
        "source_episode_ids": [],
    }
    run_id = uuid4()
    promoter, _ = _promoter(pg_pool, [artifact])

    result = await promoter.run_morning_integration(run_id)

    assert result["promoted"] == 1
    async with pg_pool.acquire() as conn:
        inserted = await conn.fetchrow(
            "SELECT agent, dream_run_id, provenance FROM memory_facts "
            "WHERE predicate = 'synthesized_insight'"
        )
    assert inserted["agent"] == "dream"
    assert inserted["dream_run_id"] == run_id
    assert inserted["provenance"] == "synthesized"
    assert (await _row(pg_pool, aged))["confidence"] == pytest.approx(0.77)
