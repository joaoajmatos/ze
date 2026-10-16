from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock


from ze_news.store import NewsStore
from ze_news.types import Article


def _make_article(**kwargs) -> Article:
    defaults = dict(
        url="https://example.com/article",
        source_key="test",
        title="Test Headline",
        summary="A short summary.",
        published_at=datetime(2026, 6, 7, 12, 0, tzinfo=timezone.utc),
        tags=["global"],
    )
    return Article(**{**defaults, **kwargs})


def _make_store():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    embedder = MagicMock()
    embedder.encode_passage.return_value = embedder.encode_query.return_value = [
        0.1
    ] * 384

    return NewsStore(pool=pool, embedder=embedder), conn


async def test_upsert_new_article():
    store, conn = _make_store()
    conn.fetchval.return_value = True

    article = _make_article()
    new_articles = await store.upsert([article])

    assert len(new_articles) == 1
    assert new_articles[0].url == article.url
    conn.fetchval.assert_called_once()


async def test_upsert_duplicate_skipped():
    store, conn = _make_store()
    conn.fetchval.return_value = False

    new_articles = await store.upsert([_make_article()])
    assert new_articles == []


async def test_upsert_conflict_update_is_not_new():
    """ON CONFLICT DO UPDATE reports 'INSERT 0 1' for an update too, so the
    command tag cannot tell a new row from a re-fetched one."""
    store, conn = _make_store()
    conn.execute.return_value = "INSERT 0 1"
    conn.fetchval.return_value = False

    new_articles = await store.upsert([_make_article()])
    assert new_articles == []


async def test_upsert_keeps_only_inserted_rows_of_a_batch():
    store, conn = _make_store()
    conn.fetchval.side_effect = [True, False, True]
    articles = [_make_article(url=f"https://example.com/{i}") for i in range(3)]

    new_articles = await store.upsert(articles)

    assert [a.url for a in new_articles] == [articles[0].url, articles[2].url]


async def test_upsert_sql_detects_insert_with_xmax():
    store, conn = _make_store()
    conn.fetchval.return_value = True
    await store.upsert([_make_article()])
    sql = conn.fetchval.call_args[0][0]
    assert "xmax = 0" in sql


async def test_upsert_empty_list():
    store, conn = _make_store()
    new_articles = await store.upsert([])
    assert new_articles == []
    conn.execute.assert_not_called()


async def test_get_recent_no_tags():
    store, conn = _make_store()
    conn.fetch.return_value = []
    results = await store.get_recent(limit=5)
    assert results == []
    conn.fetch.assert_called_once()


async def test_get_recent_with_tags():
    store, conn = _make_store()
    conn.fetch.return_value = []
    await store.get_recent(limit=5, tags=["local"])
    args = conn.fetch.call_args[0]
    assert 5 in args
    assert ["local"] in args


async def test_last_fetched_at_queries_source():
    store, conn = _make_store()
    ts = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
    conn.fetchval = AsyncMock(return_value=ts)

    result = await store.last_fetched_at("bbc_world")

    assert result == ts
    conn.fetchval.assert_called_once()
    assert conn.fetchval.call_args[0][1] == "bbc_world"


async def test_news_cluster_dedup():
    store, conn = _make_store()
    canonical = _make_article(
        url="https://example.com/original",
        summary="Leaders agreed on a ceasefire after overnight talks.",
    )
    duplicate = _make_article(
        url="https://other.com/same-story",
        summary="Leaders agreed on a ceasefire after overnight talks.",
    )

    conn.fetch.return_value = [
        {
            "url": canonical.url,
            "summary": canonical.summary,
            "embedding": [0.1] * 384,
        }
    ]
    nli_client = MagicMock()
    nli_client.scores = AsyncMock(
        return_value=[
            {"entailment": 0.90, "contradiction": 0.05, "neutral": 0.05},
            {"entailment": 0.88, "contradiction": 0.07, "neutral": 0.05},
        ]
    )

    kept = await store.dedup_new_articles(
        [duplicate],
        nli_client=nli_client,
        cosine_threshold=0.75,
        entailment_threshold=0.70,
    )

    assert kept == []
    delete_calls = [
        call
        for call in conn.execute.call_args_list
        if "DELETE FROM news_articles" in str(call)
    ]
    assert len(delete_calls) == 1


async def test_prune_returns_count():
    store, conn = _make_store()
    conn.execute.return_value = "DELETE 3"
    count = await store.prune(older_than_days=7)
    assert count == 3


async def test_search_embeds_the_user_query_as_a_query():
    store, conn = _make_store()
    conn.fetch = AsyncMock(return_value=[])

    await store.search("ai regulation")

    store._embedder.encode_query.assert_called_once_with("ai regulation")
    store._embedder.encode_passage.assert_not_called()


async def test_upsert_embeds_stored_articles_as_passages():
    store, conn = _make_store()
    conn.execute = AsyncMock(return_value="INSERT 0 1")

    await store.upsert([_make_article()])

    store._embedder.encode_passage.assert_called_with("Test Headline. A short summary.")
    store._embedder.encode_query.assert_not_called()
