from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock


from ze_news.jobs.fetch import NewsFetchJob
from ze_news.registry import SourceRegistry
from ze_news.types import Article


def _make_article(url="https://example.com/1") -> Article:
    return Article(
        url=url,
        source_key="test",
        title="Headline",
        summary="Summary.",
        published_at=datetime(2026, 6, 7, tzinfo=timezone.utc),
        tags=["global"],
    )


async def test_run_fetches_and_upserts():
    article = _make_article()
    source = MagicMock()
    source.key = "test_src"
    source.fetch = AsyncMock(return_value=[article])

    registry = SourceRegistry([source])

    store = MagicMock()
    store.last_fetched_at = AsyncMock(return_value=None)
    store.upsert = AsyncMock(return_value=[article])
    store.prune = AsyncMock(return_value=0)

    job = NewsFetchJob(registry=registry, store=store, retention_days=7)
    await job.run()

    source.fetch.assert_called_once_with(limit=50)
    store.upsert.assert_called_once()
    store.prune.assert_called_once_with(older_than_days=7)


async def test_run_skips_empty_source():
    source = MagicMock()
    source.key = "empty_src"
    source.fetch = AsyncMock(return_value=[])

    registry = SourceRegistry([source])
    store = MagicMock()
    store.last_fetched_at = AsyncMock(return_value=None)
    store.upsert = AsyncMock(return_value=[])
    store.prune = AsyncMock(return_value=0)

    job = NewsFetchJob(registry=registry, store=store)
    await job.run()

    store.upsert.assert_not_called()


async def test_run_skips_recently_fetched_source():
    source = MagicMock()
    source.key = "test_src"
    source.fetch = AsyncMock(return_value=[_make_article()])

    registry = SourceRegistry([source])
    store = MagicMock()
    store.last_fetched_at = AsyncMock(
        return_value=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    store.upsert = AsyncMock(return_value=[])
    store.prune = AsyncMock(return_value=0)

    job = NewsFetchJob(registry=registry, store=store, min_fetch_interval_minutes=30)
    await job.run()

    source.fetch.assert_not_called()
    store.upsert.assert_not_called()


async def test_run_fetches_when_source_is_stale():
    article = _make_article()
    source = MagicMock()
    source.key = "test_src"
    source.fetch = AsyncMock(return_value=[article])

    registry = SourceRegistry([source])
    store = MagicMock()
    store.last_fetched_at = AsyncMock(
        return_value=datetime.now(timezone.utc) - timedelta(minutes=45),
    )
    store.upsert = AsyncMock(return_value=[article])
    store.prune = AsyncMock(return_value=0)

    job = NewsFetchJob(registry=registry, store=store, min_fetch_interval_minutes=30)
    await job.run()

    source.fetch.assert_called_once()


async def test_run_continues_after_source_failure():
    failing = MagicMock()
    failing.key = "bad_src"
    failing.fetch = AsyncMock(return_value=[])

    article = _make_article()
    good = MagicMock()
    good.key = "good_src"
    good.fetch = AsyncMock(return_value=[article])

    registry = SourceRegistry([failing, good])
    store = MagicMock()
    store.last_fetched_at = AsyncMock(return_value=None)
    store.upsert = AsyncMock(return_value=[article])
    store.prune = AsyncMock(return_value=0)

    job = NewsFetchJob(registry=registry, store=store)
    await job.run()

    store.upsert.assert_called_once()


async def _run_job(new: list, interface):
    source = MagicMock()
    source.key = "test_src"
    source.fetch = AsyncMock(return_value=[_make_article()])
    store = MagicMock()
    store.last_fetched_at = AsyncMock(return_value=None)
    store.upsert = AsyncMock(return_value=new)
    store.prune = AsyncMock(return_value=0)
    job = NewsFetchJob(registry=SourceRegistry([source]), store=store)
    if interface is not None:
        job.bind_interface(interface)
    await job.run()


async def test_new_articles_request_a_sources_refresh_once():
    interface = MagicMock()
    interface.send_refresh = AsyncMock()

    await _run_job([_make_article()], interface)

    interface.send_refresh.assert_awaited_once_with("module:ze_news.sources")


async def test_no_new_articles_send_no_refresh():
    interface = MagicMock()
    interface.send_refresh = AsyncMock()

    await _run_job([], interface)

    interface.send_refresh.assert_not_called()


async def test_unbound_interface_completes_without_error():
    await _run_job([_make_article()], None)
