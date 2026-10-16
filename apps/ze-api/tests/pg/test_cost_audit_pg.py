"""Cost audit 2026-10 against real Postgres: the SQL the mocks cannot check."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from ze_core.telemetry.postgres import PostgresCostStore
from ze_news.store import NewsStore
from ze_news.types import Article

pytestmark = pytest.mark.pg


def _article(url: str) -> Article:
    return Article(
        url=url,
        source_key="t",
        title="Headline",
        summary="Summary",
        published_at=datetime(2026, 6, 7, tzinfo=timezone.utc),
        tags=["global"],
    )


async def test_news_upsert_reports_only_unseen_urls(pg_pool):
    async with pg_pool.acquire() as conn:
        await conn.execute("TRUNCATE news_articles")
    embedder = MagicMock()
    embedder.encode_passage.return_value = [0.1] * 768
    store = NewsStore(pool=pg_pool, embedder=embedder)

    first = await store.upsert([_article("https://e.x/a"), _article("https://e.x/b")])
    again = await store.upsert([_article("https://e.x/a"), _article("https://e.x/c")])

    assert [a.url for a in first] == ["https://e.x/a", "https://e.x/b"]
    assert [a.url for a in again] == ["https://e.x/c"]


async def _insert_cost_row(conn, gen_id: str, age: timedelta) -> None:
    await conn.execute(
        "INSERT INTO llm_cost_log (session_id, agent, flow_type, model, prompt_tokens,"
        " completion_tokens, total_tokens, duration_ms, generation_id, created_at)"
        " VALUES (NULL, 'a', 'f', 'm', 1, 1, 2, 1, $1, now() - $2::interval)",
        gen_id,
        age,
    )


async def test_fetch_pending_takes_newest_first_inside_the_window(pg_pool):
    async with pg_pool.acquire() as conn:
        await conn.execute("TRUNCATE llm_cost_log")
        await _insert_cost_row(conn, "gen-fresh", timedelta(minutes=10))
        await _insert_cost_row(conn, "gen-older", timedelta(days=1))
        await _insert_cost_row(conn, "gen-expired", timedelta(days=10))
        await _insert_cost_row(conn, "gen-too-new", timedelta(seconds=10))
        await _insert_cost_row(conn, "gen-dead", timedelta(minutes=20))
    store = PostgresCostStore(pg_pool)

    rows = await store.fetch_pending(
        batch_size=50,
        min_age_seconds=120,
        max_age_seconds=3 * 86400,
        exclude_generation_ids=["gen-dead"],
    )

    assert [r["generation_id"] for r in rows] == ["gen-fresh", "gen-older"]


async def test_update_cost_reports_whether_a_row_changed(pg_pool):
    async with pg_pool.acquire() as conn:
        await conn.execute("TRUNCATE llm_cost_log")
        await _insert_cost_row(conn, "gen-1", timedelta(minutes=10))
        row_id = await conn.fetchval("SELECT id FROM llm_cost_log")
    store = PostgresCostStore(pg_pool)

    assert await store.update_cost(row_id, 0.000236) is True
    assert await store.update_cost(row_id, 0.000236) is True  # same row, still one row
    from uuid import uuid4

    assert await store.update_cost(uuid4(), 0.1) is False
    async with pg_pool.acquire() as conn:
        assert float(await conn.fetchval("SELECT cost_usd FROM llm_cost_log")) == (
            pytest.approx(0.000236)
        )
