"""Tests for dream/promoter.py — DreamPromoter (Claim Topology, FR-010/FR-011)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_memory.dream.promoter import DreamPromoter
from ze_memory.dream.types import ArtifactType


class _AsyncCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_):
        pass


def _make_pool(fetch_rows=None):
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=fetch_rows or [])
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": uuid4()})
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncCtx(conn))
    return pool, conn


def _make_promoter(pool):
    return DreamPromoter(pool=pool, dream_store=AsyncMock(), embedder=None, settings=None)


# ── _run_confidence_decay (fetch-decay-write, T015) ─────────────────────────


async def test_confidence_decay_applies_shared_time_linear_rate():
    row = {"id": uuid4(), "confidence": 0.8, "reviewed": True, "contradicted": False}
    pool, conn = _make_pool(fetch_rows=[row])
    promoter = _make_promoter(pool)

    await promoter._run_confidence_decay()

    conn.execute.assert_awaited_once()
    args = conn.execute.call_args.args
    assert args[1] == row["id"]
    new_confidence = args[2]
    assert round(new_confidence, 2) == 0.77


async def test_confidence_decay_below_050_flips_reviewed_false():
    row = {"id": uuid4(), "confidence": 0.52, "reviewed": True, "contradicted": False}
    pool, conn = _make_pool(fetch_rows=[row])
    promoter = _make_promoter(pool)

    await promoter._run_confidence_decay()

    args = conn.execute.call_args.args
    assert round(args[2], 2) == 0.49
    assert args[3] is False  # reviewed


async def test_confidence_decay_below_025_flips_contradicted_true():
    row = {"id": uuid4(), "confidence": 0.27, "reviewed": False, "contradicted": False}
    pool, conn = _make_pool(fetch_rows=[row])
    promoter = _make_promoter(pool)

    await promoter._run_confidence_decay()

    args = conn.execute.call_args.args
    assert round(args[2], 2) == 0.24
    assert args[4] is True  # contradicted


async def test_confidence_decay_no_eligible_rows_no_write():
    pool, conn = _make_pool(fetch_rows=[])
    promoter = _make_promoter(pool)

    await promoter._run_confidence_decay()

    conn.execute.assert_not_awaited()


# ── _promote — claim_kind on the promoter's own INSERT (T015B) ─────────────


async def test_promote_synthesized_insight_writes_inference_claim_kind():
    pool, conn = _make_pool()
    promoter = _make_promoter(pool)

    row = {
        "id": uuid4(),
        "artifact_type": ArtifactType.SYNTHESIZED_INSIGHT.value,
        "content": "User seems to prefer async communication",
        "source_fact_ids": [],
    }
    await promoter._promote(row, run_id=uuid4(), valid_days=90)

    conn.fetchrow.assert_awaited_once()
    query = conn.fetchrow.call_args.args[0]
    assert "claim_kind" in query
    assert "'inference'" in query
