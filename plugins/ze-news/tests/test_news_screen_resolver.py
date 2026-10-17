import hashlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from ze_news import article_ref_id
from ze_news.screen_resolvers import NewsArticleScreenResolver
from ze_news.store import NewsStore
from ze_news.types import Article
from ze_sdk.screen import ResolveContext, ScreenRef, ScreenStatus

CTX = ResolveContext(now=datetime(2026, 10, 17, tzinfo=UTC))
URL = "https://exemplo.pt/notícias/ação-é-rápida?x=1"


def test_article_ref_id_is_the_md5_hex_of_the_utf8_url_and_fits_the_ref_cap():
    ref = article_ref_id(URL)
    assert ref == hashlib.md5(URL.encode("utf-8")).hexdigest()
    assert len(ref) == 32 <= 64


async def test_store_looks_the_article_up_with_the_same_md5_it_emits():
    row = {
        "url": URL,
        "source_key": "pt",
        "title": "Ação",
        "summary": "s",
        "published_at": datetime(2026, 10, 1, tzinfo=UTC),
        "tags": [],
        "credibility_analysis": None,
    }
    record = MagicMock()
    record.__getitem__ = lambda self, k: row[k]
    record.keys = lambda: list(row)
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=record)
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    article = await NewsStore(pool, embedder=MagicMock()).get_by_ref(
        article_ref_id(URL)
    )
    sql, param = conn.fetchrow.await_args.args
    assert "md5(url) = $1" in sql
    assert param == hashlib.md5(URL.encode("utf-8")).hexdigest()
    assert article is not None and article.url == URL


async def test_resolver_line_and_missing():
    article = Article(
        url=URL,
        source_key="pt",
        title="Ação\nrápida",
        summary="s",
        published_at=datetime(2026, 10, 1, tzinfo=UTC),
    )
    store = AsyncMock()
    store.get_by_ref = AsyncMock(return_value=article)
    ref = ScreenRef(kind="news_article", id=article_ref_id(URL))
    [line] = await NewsArticleScreenResolver(store).resolve([ref], CTX)
    assert line.label == "Ação rápida" and line.summary == "pt, published 2026-10-01"
    store.get_by_ref = AsyncMock(return_value=None)
    [gone] = await NewsArticleScreenResolver(store).resolve([ref], CTX)
    assert gone.status is ScreenStatus.MISSING
