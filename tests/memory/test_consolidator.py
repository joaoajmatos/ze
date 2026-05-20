import json
import pathlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import numpy as np
import pytest

from ze.memory.consolidator import MemoryConsolidator, _mean_embedding, _parse_count
from ze.memory.types import ConsolidationReport
from ze.settings import Settings


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_settings():
    from ze.settings import get_settings
    get_settings.cache_clear()
    real_config = pathlib.Path(__file__).parent.parent.parent / "config"
    return Settings(
        openrouter_api_key="test-key",
        database_url="postgresql://ze:ze@localhost:5432/ze",
        database_url_sync="postgresql+psycopg2://ze:ze@localhost:5432/ze",
        config_dir=real_config,
    )


def make_conn():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value="DELETE 0")
    return conn


def make_pool(conn=None):
    if conn is None:
        conn = make_conn()
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=cm)
    return pool


def make_txn_pool(conn):
    """Pool where conn.transaction() works as an async context manager."""
    txn_cm = AsyncMock()
    txn_cm.__aenter__ = AsyncMock(return_value=None)
    txn_cm.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=txn_cm)
    return make_pool(conn)


def make_embedder(vec=None):
    embedder = MagicMock()
    embedder.encode = MagicMock(return_value=vec if vec is not None else np.zeros(384))
    return embedder


def make_consolidator(pool=None, embedder=None, client=None, settings=None):
    return MemoryConsolidator(
        pool=pool or make_pool(),
        embedder=embedder or make_embedder(),
        openrouter_client=client or AsyncMock(),
        settings=settings or make_settings(),
    )


def norm_vec(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def _emb_json(v: np.ndarray) -> str:
    return json.dumps(v.tolist())


def make_fact_row(similarity_vec: np.ndarray | None = None, **overrides):
    vec = similarity_vec if similarity_vec is not None else norm_vec(np.random.rand(384))
    defaults = {
        "id": uuid4(),
        "key": "name",
        "value": "Alice",
        "agent": "global",
        "confidence": 1.0,
        "reviewed": False,
        "contradicted": False,
        "updated_at": datetime.now(timezone.utc),
        "embedding": _emb_json(vec),
    }
    defaults.update(overrides)
    return defaults


def make_episode_row(**overrides):
    vec = norm_vec(np.random.rand(384))
    defaults = {
        "id": uuid4(),
        "agent": "research",
        "prompt": "what is AI?",
        "response": "AI is ...",
        "summary": "Discussion about AI.",
        "embedding": _emb_json(vec),
        "created_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return defaults


# ── dedup_facts ───────────────────────────────────────────────────────────────

async def test_dedup_silent_merge():
    base = norm_vec(np.ones(384))
    fact_a = make_fact_row(similarity_vec=base, key="pref", value="cats", updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    fact_b = make_fact_row(similarity_vec=base, key="pref", value="cats too", updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))

    conn = make_conn()
    conn.fetch = AsyncMock(return_value=[fact_a, fact_b])
    client = AsyncMock()

    c = make_consolidator(pool=make_pool(conn), client=client)
    merged = await c.dedup_facts()

    assert merged == 1
    client.complete.assert_not_called()
    conn.execute.assert_called()
    # the older fact (fact_b) should be marked contradicted
    call_args = [str(call) for call in conn.execute.call_args_list]
    assert any(str(fact_b["id"]) in a for a in call_args)


async def test_dedup_llm_merge():
    # a = unit vector along first axis; b = [0.9, sqrt(0.19), 0...] is also
    # unit length, and dot(a, b) = 0.9 — in the LLM-merge range (0.85, 0.95).
    a = np.array([1.0] + [0.0] * 383)
    b = np.array([0.9, float(np.sqrt(1 - 0.9 ** 2))] + [0.0] * 382)
    similarity = float(np.dot(a, b))
    assert 0.85 < similarity < 0.95, f"test setup: similarity={similarity} not in range"

    fact_a = make_fact_row(similarity_vec=a, key="city", value="Lisbon", updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    fact_b = make_fact_row(similarity_vec=b, key="hometown", value="Lisboa", updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))

    conn = make_conn()
    conn.fetch = AsyncMock(return_value=[fact_a, fact_b])
    client = AsyncMock()
    client.complete = AsyncMock(return_value='{"key": "city", "value": "Lisbon (Lisboa)"}')
    embedder = make_embedder(vec=norm_vec(np.ones(384)))

    c = make_consolidator(pool=make_pool(conn), embedder=embedder, client=client)
    merged = await c.dedup_facts()

    assert merged == 1
    client.complete.assert_called_once()
    # Both originals should be marked contradicted
    execute_calls = conn.execute.call_args_list
    contradicted_ids = set()
    for call in execute_calls:
        args = call[0]
        if args and "contradicted" in str(args[0]):
            contradicted_ids.add(args[1])
    assert fact_a["id"] in contradicted_ids
    assert fact_b["id"] in contradicted_ids


async def test_dedup_skips_reviewed():
    base = norm_vec(np.ones(384))
    fact_a = make_fact_row(similarity_vec=base, reviewed=True)
    fact_b = make_fact_row(similarity_vec=base, reviewed=False)

    conn = make_conn()
    conn.fetch = AsyncMock(return_value=[fact_a, fact_b])
    client = AsyncMock()

    c = make_consolidator(pool=make_pool(conn), client=client)
    merged = await c.dedup_facts()

    assert merged == 0
    client.complete.assert_not_called()
    conn.execute.assert_not_called()


async def test_dedup_llm_failure_fallback():
    base = norm_vec(np.ones(384))
    # similarity = 1.0, above silent threshold — but let's use a pair in the
    # LLM range to confirm the fallback path is exercised
    a = norm_vec(np.array([1.0] + [0.0] * 383))
    b = norm_vec(np.array([0.9, 0.1] + [0.0] * 382))

    fact_a = make_fact_row(similarity_vec=a, updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    fact_b = make_fact_row(similarity_vec=b, updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))

    conn = make_conn()
    conn.fetch = AsyncMock(return_value=[fact_a, fact_b])
    client = AsyncMock()
    client.complete = AsyncMock(side_effect=Exception("openrouter error"))

    c = make_consolidator(pool=make_pool(conn), client=client)
    merged = await c.dedup_facts()

    # Falls back to silent merge — still resolves the pair
    assert merged == 1
    conn.execute.assert_called()


# ── expire_facts ──────────────────────────────────────────────────────────────

async def test_expire_grace_delete():
    conn = make_conn()
    conn.execute = AsyncMock(side_effect=["DELETE 2", "DELETE 0", "UPDATE 0"])
    c = make_consolidator(pool=make_pool(conn))

    soft, hard = await c.expire_facts()

    assert hard == 2
    assert soft == 0


async def test_expire_contradicted_cleanup():
    conn = make_conn()
    conn.execute = AsyncMock(side_effect=["DELETE 0", "DELETE 3", "UPDATE 0"])
    c = make_consolidator(pool=make_pool(conn))

    soft, hard = await c.expire_facts()

    assert hard == 3
    assert soft == 0


async def test_expire_soft_expire():
    conn = make_conn()
    conn.execute = AsyncMock(side_effect=["DELETE 0", "DELETE 0", "UPDATE 4"])
    c = make_consolidator(pool=make_pool(conn))

    soft, hard = await c.expire_facts()

    assert soft == 4
    assert hard == 0


async def test_expire_skips_reviewed():
    conn = make_conn()
    executed_sqls: list[str] = []
    async def capture_execute(sql, *args):
        executed_sqls.append(sql)
        return "DELETE 0" if "DELETE" in sql else "UPDATE 0"
    conn.execute = capture_execute

    c = make_consolidator(pool=make_pool(conn))
    await c.expire_facts()

    assert len(executed_sqls) == 3
    # Grace-delete and contradicted-cleanup do not need reviewed=false (they
    # target facts already in a terminal state). Only the soft-expire UPDATE
    # must guard against expiring reviewed=true facts.
    soft_expire_sql = executed_sqls[2]
    assert "reviewed = false" in soft_expire_sql


# ── archive_episodes ──────────────────────────────────────────────────────────

async def test_archive_below_minimum():
    # Only 5 old episodes — below default min of 10, should skip
    rows = [make_episode_row() for _ in range(5)]
    conn = make_conn()
    conn.fetch = AsyncMock(return_value=rows)
    client = AsyncMock()

    c = make_consolidator(pool=make_pool(conn), client=client)
    archived, deleted = await c.archive_episodes()

    assert archived == 0
    assert deleted == 0
    client.complete.assert_not_called()


async def test_archive_batch():
    rows = [make_episode_row() for _ in range(20)]
    conn = make_conn()
    # First call: 20 rows. Second call (next loop iteration): 0 rows → stops.
    conn.fetch = AsyncMock(side_effect=[rows, []])
    conn.execute = AsyncMock(return_value="DELETE 20")
    txn_pool = make_txn_pool(conn)

    client = AsyncMock()
    client.complete = AsyncMock(return_value="Summary of 20 episodes.")

    c = make_consolidator(pool=txn_pool, client=client)
    archived, deleted = await c.archive_episodes()

    assert archived == 1
    assert deleted == 20
    client.complete.assert_called_once()


async def test_archive_haiku_failure():
    rows = [make_episode_row() for _ in range(20)]
    conn = make_conn()
    conn.fetch = AsyncMock(return_value=rows)
    client = AsyncMock()
    client.complete = AsyncMock(side_effect=Exception("haiku error"))

    c = make_consolidator(pool=make_pool(conn), client=client)
    archived, deleted = await c.archive_episodes()

    assert archived == 0
    assert deleted == 0
    conn.execute.assert_not_called()


# ── run ───────────────────────────────────────────────────────────────────────

async def test_run_full():
    conn = make_conn()
    # dedup_facts: fewer than 2 facts → skips
    conn.fetch = AsyncMock(return_value=[])
    # expire_facts: three execute calls
    conn.execute = AsyncMock(side_effect=["DELETE 1", "DELETE 2", "UPDATE 3"] * 10)

    client = AsyncMock()

    c = make_consolidator(pool=make_pool(conn), client=client)

    with patch.object(c, "dedup_facts", AsyncMock(return_value=5)), \
         patch.object(c, "expire_facts", AsyncMock(return_value=(3, 4))), \
         patch.object(c, "archive_episodes", AsyncMock(return_value=(2, 40))):
        report = await c.run()

    assert isinstance(report, ConsolidationReport)
    assert report.facts_merged == 5
    assert report.facts_soft_expired == 3
    assert report.facts_hard_deleted == 4
    assert report.episodes_archived == 2
    assert report.episodes_deleted == 40
    assert report.duration_ms >= 0


# ── unit helpers ──────────────────────────────────────────────────────────────

def test_parse_count():
    assert _parse_count("DELETE 3") == 3
    assert _parse_count("UPDATE 0") == 0
    assert _parse_count("") == 0


def test_mean_embedding_normalised():
    vecs = [norm_vec(np.random.rand(384)) for _ in range(5)]
    result = _mean_embedding(vecs)
    assert abs(np.linalg.norm(result) - 1.0) < 1e-6


def test_mean_embedding_empty():
    result = _mean_embedding([])
    assert result.shape == (384,)
    assert np.all(result == 0)


# ── synthesise_profile ────────────────────────────────────────────────────────

def _make_profile_conn(fact_rows=None, episode_rows=None, profile_row=None):
    """Return a conn where three sequential fetchrow/fetch calls return profile data."""
    conn = make_conn()
    conn.fetch = AsyncMock(side_effect=[
        fact_rows or [],
        episode_rows or [],
    ])
    conn.fetchrow = AsyncMock(return_value=profile_row)
    conn.execute = AsyncMock(return_value="UPDATE 1")
    return conn


async def test_synthesise_profile_writes_profile():
    fact_rows = [
        {"key": "name", "value": "Alice"},
        {"key": "city", "value": "Lisbon"},
        {"key": "lang", "value": "Portuguese"},
    ]
    episode_rows = [{"summary": "Discussed travel plans.", "response": "..."}]
    profile_row = {
        "preferences": "", "habits": "", "topics": "",
        "relationships": "", "goals": "", "version": 0,
    }

    conn = _make_profile_conn(fact_rows, episode_rows, profile_row)
    client = AsyncMock()
    client.complete = AsyncMock(return_value=json.dumps({
        "preferences": "Prefers concise answers.",
        "habits": "Works in the evenings.",
        "topics": "Travel and languages.",
        "relationships": "No relationships mentioned.",
        "goals": "Learn Portuguese.",
    }))

    c = make_consolidator(pool=make_pool(conn), client=client)
    result = await c.synthesise_profile()

    assert result is True
    client.complete.assert_called_once()
    conn.execute.assert_called_once()
    sql = conn.execute.call_args[0][0]
    assert "UPDATE user_profile" in sql


async def test_synthesise_profile_skips_sparse():
    # Fewer than min_facts (3) reviewed facts and no episodes
    conn = _make_profile_conn(fact_rows=[], episode_rows=[])
    client = AsyncMock()

    c = make_consolidator(pool=make_pool(conn), client=client)
    result = await c.synthesise_profile()

    assert result is False
    client.complete.assert_not_called()
    conn.execute.assert_not_called()


async def test_synthesise_profile_haiku_failure():
    fact_rows = [{"key": f"k{i}", "value": "v"} for i in range(3)]
    conn = _make_profile_conn(fact_rows=fact_rows, profile_row={
        "preferences": "", "habits": "", "topics": "",
        "relationships": "", "goals": "", "version": 0,
    })
    client = AsyncMock()
    client.complete = AsyncMock(side_effect=Exception("haiku unavailable"))

    c = make_consolidator(pool=make_pool(conn), client=client)
    result = await c.synthesise_profile()

    assert result is False
    conn.execute.assert_not_called()


async def test_synthesise_profile_bad_json():
    fact_rows = [{"key": f"k{i}", "value": "v"} for i in range(3)]
    conn = _make_profile_conn(fact_rows=fact_rows, profile_row={
        "preferences": "", "habits": "", "topics": "",
        "relationships": "", "goals": "", "version": 0,
    })
    client = AsyncMock()
    client.complete = AsyncMock(return_value="not valid json at all")

    c = make_consolidator(pool=make_pool(conn), client=client)
    result = await c.synthesise_profile()

    assert result is False
    conn.execute.assert_not_called()


async def test_synthesise_profile_truncates_long_sections():
    fact_rows = [{"key": f"k{i}", "value": "v"} for i in range(3)]
    conn = _make_profile_conn(fact_rows=fact_rows, profile_row={
        "preferences": "", "habits": "", "topics": "",
        "relationships": "", "goals": "", "version": 2,
    })
    long_text = "x" * 600
    client = AsyncMock()
    client.complete = AsyncMock(return_value=json.dumps({
        "preferences": long_text,
        "habits": long_text,
        "topics": long_text,
        "relationships": long_text,
        "goals": long_text,
    }))

    c = make_consolidator(pool=make_pool(conn), client=client)
    result = await c.synthesise_profile()

    assert result is True
    # Check that the stored values are truncated to 400 chars
    call_args = conn.execute.call_args[0]
    for section_val in call_args[1:6]:
        assert len(section_val) <= 400


async def test_run_includes_profile_updated_flag():
    conn = make_conn()
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(side_effect=["DELETE 0", "DELETE 0", "UPDATE 0"] * 10)

    c = make_consolidator(pool=make_pool(conn))

    with patch.object(c, "dedup_facts", AsyncMock(return_value=0)), \
         patch.object(c, "expire_facts", AsyncMock(return_value=(0, 0))), \
         patch.object(c, "archive_episodes", AsyncMock(return_value=(0, 0))), \
         patch.object(c, "synthesise_profile", AsyncMock(return_value=True)):
        report = await c.run()

    assert report.profile_updated is True
