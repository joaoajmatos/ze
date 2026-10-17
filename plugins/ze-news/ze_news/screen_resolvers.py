"""Screen resolver for news articles (phase 195)."""

from __future__ import annotations

from typing import Any

from ze_sdk.screen import (
    ResolveContext,
    ScreenLine,
    ScreenPosture,
    ScreenRef,
    ScreenResolver,
    as_utc,
    resolve_each,
    sanitize_text,
)


class NewsArticleScreenResolver:
    kinds = frozenset({"news_article"})

    def __init__(self, news_store: Any) -> None:
        self._news = news_store

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return await resolve_each(refs, self._load)

    async def _load(self, ref: ScreenRef) -> ScreenLine | None:
        article = await self._news.get_by_ref(ref.id)
        if article is None:
            return None
        published = as_utc(article.published_at)
        return ScreenLine(
            ref=ref,
            label=sanitize_text(article.title, 120),
            summary=f"{sanitize_text(article.source_key, 40)}, published {published:%Y-%m-%d}",
            posture=ScreenPosture(source="news", updated_at=published),
        )


def build_screen_resolvers(*, news_store: Any) -> list[ScreenResolver]:
    return [NewsArticleScreenResolver(news_store)]
