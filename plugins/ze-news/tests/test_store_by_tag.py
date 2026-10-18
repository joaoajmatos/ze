from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from ze_news.store import NewsStore


def _store():
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetch.return_value = [
        {
            "url": "https://example.com/a",
            "source_key": "bbc",
            "title": "Heat wave",
            "summary": "s",
            "published_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
            "tags": ["climate"],
            "credibility_analysis": None,
        }
    ]
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return NewsStore(pool=pool, embedder=MagicMock()), conn


async def test_by_tag_matches_the_tag_exactly_newest_first_capped_at_eight():
    store, conn = _store()

    articles = await store.by_tag("climate")

    sql, *args = conn.fetch.call_args.args
    assert "tags && ARRAY[$1]" in sql
    assert "lower(" not in sql.lower()
    assert "ORDER BY published_at DESC" in sql
    assert args == ["climate", 8]
    assert [a.title for a in articles] == ["Heat wave"]


async def test_by_tag_honours_a_smaller_limit():
    store, conn = _store()

    await store.by_tag("climate", limit=3)

    assert conn.fetch.call_args.args[2] == 3
