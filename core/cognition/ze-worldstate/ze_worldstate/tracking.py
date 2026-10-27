from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from ze_logging import get_logger
from ze_memory.graph.store import GraphStore

from ze_worldstate.extraction import resolve_entities, _whole_days
from ze_worldstate.lifecycle import DeclaredStamp, LoopDraft, LoopLifecycle
from ze_worldstate.matching import find_matching_loop
from ze_worldstate.store import LoopStore
from ze_worldstate.types import (
    LoopProvenance,
    OpenLoop,
    SourceKey,
    TrackOutcome,
    TrackResult,
)

log = get_logger(__name__)

DEFAULT_WINDOW_DAYS = DeclaredStamp.DEFAULT_WINDOW_DAYS
MAX_WINDOW_DAYS = 365
MAX_TITLE_CHARS = 120


def _normalize_title(raw: str) -> str:
    title = re.sub(r"\s+", " ", str(raw or "")).strip()
    if len(title) <= MAX_TITLE_CHARS:
        return title
    cut = title[:MAX_TITLE_CHARS]
    if title[MAX_TITLE_CHARS] != " " and " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip()


def _clamp_window(raw: Any) -> int:
    days = _whole_days(raw)
    if days is None:
        return DEFAULT_WINDOW_DAYS
    return min(days, MAX_WINDOW_DAYS)


class LoopTracker:
    """Starts tracking an open loop the user explicitly asked Ze to keep in mind."""

    def __init__(
        self,
        loop_store: LoopStore,
        lifecycle: LoopLifecycle,
        graph_store: GraphStore | None,
        entity_resolver: Any,
        embedder: Any,
    ) -> None:
        self._store = loop_store
        self._lifecycle = lifecycle
        self._graph = graph_store
        self._resolver = entity_resolver
        self._embedder = embedder

    async def track(
        self, title: str, window_days: Any = 0, session_id: str | None = None
    ) -> TrackResult:
        title = _normalize_title(title)
        if not title:
            return TrackResult(ok=False, error="a loop needs a title")
        window = _clamp_window(window_days)
        try:
            result = await self._track(title, window, session_id)
        except Exception as exc:
            log.warning("loop_track_failed", error=str(exc))
            return TrackResult(ok=False, error="could not save the loop")
        log.info("loop_tracked", outcome=result.outcome, loop_id=str(result.loop.id))
        return result

    async def _track(
        self, title: str, window: int, session_id: str | None
    ) -> TrackResult:
        entity_ids = await resolve_entities(self._resolver, title)
        match = await self._find_match(title, entity_ids)

        if match is None:
            source = (
                SourceKey(LoopProvenance.CONVERSATION, session_id)
                if session_id
                else None
            )
            loop = await self._lifecycle.create_declared(
                LoopDraft(
                    title=title,
                    provenance=LoopProvenance.USER_DECLARED,
                    entity_ids=tuple(entity_ids),
                    source=source,
                ),
                window_days=window,
            )
            return TrackResult(ok=True, outcome=TrackOutcome.CREATED, loop=loop)

        tracked = await self._lifecycle.track(
            match.id, window_days=window, entity_ids=entity_ids
        )
        return TrackResult(ok=True, outcome=tracked.outcome, loop=tracked.loop)

    async def _find_match(self, title: str, entity_ids: list[UUID]) -> OpenLoop | None:
        if self._graph is None:
            return None
        return await find_matching_loop(
            entity_ids,
            title,
            loop_store=self._store,
            graph_store=self._graph,
            embedder=self._embedder,
            states=["suspected", "active", "drifting"],
        )
