from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze_core.memory.consolidator import MemoryConsolidator
from ze_core.memory.types import ConsolidationReport


# ── helpers ───────────────────────────────────────────────────────────────────

def _conn():
    c = AsyncMock()
    c.fetch = AsyncMock(return_value=[])
    c.fetchrow = AsyncMock(return_value=None)
    c.execute = AsyncMock(return_value="UPDATE 0")
    return c


def _pool(conn):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=cm)
    return pool


def _embedder(vec=None):
    v = vec or [1.0, 0.0]
    e = MagicMock()
    e.encode = MagicMock(return_value=v)
    return e


def _client(response="{}"):
    c = AsyncMock()
    c.complete = AsyncMock(return_value=response)
    return c


def _consolidator(conn=None, client=None, settings=None, embedder=None):
    c = conn or _conn()
    return MemoryConsolidator(
        pool=_pool(c),
        embedder=embedder or _embedder(),
        openrouter_client=client or _client(),
        settings=settings,
    ), c


def _now():
    return datetime.now(timezone.utc)


def _fact_row(key="k", value="v", confidence=1.0):
    return {
        "id": uuid4(),
        "key": key,
        "value": value,
        "agent": "global",
        "confidence": confidence,
    }


# ── TestRun ───────────────────────────────────────────────────────────────────

class TestRun:
    async def test_returns_consolidation_report(self):
        conn = _conn()
        conn.fetch = AsyncMock(return_value=[])
        consolidator, _ = _consolidator(conn=conn)
        report = await consolidator.run()
        assert isinstance(report, ConsolidationReport)

    async def test_duration_ms_set(self):
        conn = _conn()
        conn.fetch = AsyncMock(return_value=[])
        consolidator, _ = _consolidator(conn=conn)
        report = await consolidator.run()
        assert report.duration_ms >= 0

    async def test_empty_store_all_zeros(self):
        conn = _conn()
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock(return_value="UPDATE 0")
        consolidator, _ = _consolidator(conn=conn)
        report = await consolidator.run()
        assert report.facts_merged == 0
        assert report.facts_soft_expired == 0
        assert report.facts_hard_deleted == 0
        assert report.episodes_archived == 0
        assert report.profile_updated is False


# ── TestDedupFacts ────────────────────────────────────────────────────────────

class TestDedupFacts:
    async def test_no_facts_returns_zero(self):
        conn = _conn()
        conn.fetch = AsyncMock(return_value=[])
        consolidator, _ = _consolidator(conn=conn)
        assert await consolidator.dedup_facts() == 0

    async def test_single_fact_returns_zero(self):
        conn = _conn()
        conn.fetch = AsyncMock(return_value=[_fact_row()])
        consolidator, _ = _consolidator(conn=conn)
        assert await consolidator.dedup_facts() == 0

    async def test_silent_merge_high_similarity(self):
        # Both facts get identical vectors → cosine similarity = 1.0 > 0.95
        conn = _conn()
        rows = [
            _fact_row("k1", "fact one", confidence=0.9),
            _fact_row("k2", "fact two", confidence=1.0),
        ]
        conn.fetch = AsyncMock(return_value=rows)
        consolidator, _ = _consolidator(conn=conn, embedder=_embedder([1.0, 0.0]))
        merged = await consolidator.dedup_facts()
        assert merged == 1
        # Lower-confidence fact (rows[0]) should be contradicted
        update_calls = [str(c) for c in conn.execute.await_args_list]
        assert any("contradicted = true" in s for s in update_calls)

    async def test_llm_merge_medium_similarity(self):
        # First pair: similarity ≈ 0.87 (between merge_llm and merge_silent)
        conn = _conn()
        rows = [_fact_row("k1", "a"), _fact_row("k2", "b")]
        conn.fetch = AsyncMock(return_value=rows)
        # Embedder returns slightly different vectors so similarity is < 0.95 but > 0.85
        vecs = [[1.0, 0.0], [0.87, 0.49]]  # cos sim ≈ 0.87
        call_count = 0

        def _encode(text):
            nonlocal call_count
            v = vecs[call_count % len(vecs)]
            call_count += 1
            return v

        embedder = MagicMock()
        embedder.encode = MagicMock(side_effect=_encode)
        client = _client(response="merged fact")
        consolidator, _ = _consolidator(conn=conn, embedder=embedder, client=client)
        merged = await consolidator.dedup_facts()
        assert merged == 1
        client.complete.assert_awaited_once()

    async def test_low_similarity_no_merge(self):
        conn = _conn()
        rows = [_fact_row("k1", "a"), _fact_row("k2", "b")]
        conn.fetch = AsyncMock(return_value=rows)
        # Orthogonal vectors → similarity = 0.0
        vecs = [[1.0, 0.0], [0.0, 1.0]]
        idx = [0]

        def _encode(text):
            v = vecs[idx[0] % len(vecs)]
            idx[0] += 1
            return v

        embedder = MagicMock()
        embedder.encode = MagicMock(side_effect=_encode)
        consolidator, _ = _consolidator(conn=conn, embedder=embedder)
        assert await consolidator.dedup_facts() == 0


# ── TestExpireFacts ───────────────────────────────────────────────────────────

class TestExpireFacts:
    async def test_returns_counts_from_sql(self):
        conn = _conn()
        conn.execute = AsyncMock(side_effect=["UPDATE 3", "DELETE 2"])
        consolidator, _ = _consolidator(conn=conn)
        soft, hard = await consolidator.expire_facts()
        assert soft == 3
        assert hard == 2

    async def test_sql_includes_ttl_interval(self):
        settings = {"memory": {"unreviewed_ttl_days": 45, "contradicted_ttl_days": 15}}
        conn = _conn()
        conn.execute = AsyncMock(return_value="UPDATE 0")
        consolidator, _ = _consolidator(conn=conn, settings=settings)
        await consolidator.expire_facts()
        calls_sql = [str(c) for c in conn.execute.await_args_list]
        assert any("45" in s for s in calls_sql)
        assert any("15" in s for s in calls_sql)

    async def test_zero_counts_on_empty_result(self):
        conn = _conn()
        conn.execute = AsyncMock(return_value=None)
        consolidator, _ = _consolidator(conn=conn)
        soft, hard = await consolidator.expire_facts()
        assert soft == 0
        assert hard == 0


# ── TestArchiveEpisodes ───────────────────────────────────────────────────────

class TestArchiveEpisodes:
    async def test_skips_llm_when_below_min_batch(self):
        conn = _conn()
        conn.fetch = AsyncMock(return_value=[])  # 0 candidates < 10 min_batch
        client = _client()
        consolidator, _ = _consolidator(conn=conn, client=client)
        archived, _ = await consolidator.archive_episodes()
        assert archived == 0
        client.complete.assert_not_awaited()

    async def test_archives_when_batch_full(self):
        conn = _conn()
        candidates = [
            {
                "id": uuid4(), "prompt": f"p{i}", "response": f"r{i}", "summary": None
            }
            for i in range(10)
        ]
        conn.fetch = AsyncMock(return_value=candidates)
        conn.execute = AsyncMock(return_value="DELETE 10")
        client = _client(response="archive summary")
        consolidator, _ = _consolidator(conn=conn, client=client)
        settings = {"memory": {"episode_recency_days": 14, "episode_min_archive_batch": 10, "episode_archive_batch": 20}}
        consolidator._settings = settings
        archived, _ = await consolidator.archive_episodes()
        assert archived == 10
        client.complete.assert_awaited_once()

    async def test_llm_failure_returns_zero(self):
        conn = _conn()
        candidates = [{"id": uuid4(), "prompt": "p", "response": "r", "summary": None} for _ in range(10)]
        conn.fetch = AsyncMock(return_value=candidates)
        client = AsyncMock()
        client.complete = AsyncMock(side_effect=Exception("llm down"))
        consolidator, _ = _consolidator(conn=conn, client=client)
        consolidator._settings = {"memory": {"episode_recency_days": 14, "episode_min_archive_batch": 10, "episode_archive_batch": 20}}
        archived, deleted = await consolidator.archive_episodes()
        assert archived == 0
        assert deleted == 0


# ── TestUpdateProfile ─────────────────────────────────────────────────────────

class TestUpdateProfile:
    async def test_returns_false_when_no_data(self):
        conn = _conn()
        conn.fetch = AsyncMock(return_value=[])
        consolidator, _ = _consolidator(conn=conn)
        assert await consolidator.update_profile() is False

    async def test_upserts_valid_profile(self):
        conn = _conn()
        conn.fetch = AsyncMock(side_effect=[
            [{"key": "name", "value": "Alice"}],
            [{"summary": "discussed tech"}],
        ])
        profile_json = '{"preferences":"p","habits":"h","topics":"t","relationships":"r","goals":"g"}'
        client = _client(response=profile_json)
        consolidator, _ = _consolidator(conn=conn, client=client)
        result = await consolidator.update_profile()
        assert result is True
        conn.execute.assert_awaited_once()

    async def test_invalid_json_returns_false(self):
        conn = _conn()
        conn.fetch = AsyncMock(side_effect=[
            [{"key": "name", "value": "Alice"}],
            [],
        ])
        client = _client(response="not json at all")
        consolidator, _ = _consolidator(conn=conn, client=client)
        assert await consolidator.update_profile() is False

    async def test_missing_keys_returns_false(self):
        conn = _conn()
        conn.fetch = AsyncMock(side_effect=[
            [{"key": "name", "value": "Alice"}],
            [],
        ])
        client = _client(response='{"preferences":"p"}')
        consolidator, _ = _consolidator(conn=conn, client=client)
        assert await consolidator.update_profile() is False
