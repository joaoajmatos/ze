from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from ze_collision.detect import submit_and_detect_collisions
from ze_logging import get_logger
from ze_memory.graph.store import GraphStore

from ze_worldstate import drift
from ze_worldstate.contribution import loop_to_contribution
from ze_worldstate.extraction import resolve_entities, _whole_days
from ze_worldstate.matching import find_matching_loop
from ze_worldstate.store import LoopStore
from ze_worldstate.types import (
    DECLARED_CONFIDENCE,
    LoopClaimKind,
    LoopProvenance,
    LoopState,
    OpenLoop,
    TrackOutcome,
    TrackResult,
)

log = get_logger(__name__)

DEFAULT_WINDOW_DAYS = drift.DEFAULT_DRIFT_WINDOW_DAYS
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
        graph_store: GraphStore | None,
        entity_resolver: Any,
        embedder: Any,
        collision_store: Any = None,
        nli_client: Any = None,
    ) -> None:
        self._store = loop_store
        self._graph = graph_store
        self._resolver = entity_resolver
        self._embedder = embedder
        self._collision_store = collision_store
        self._nli = nli_client

    async def track(self, title: str, window_days: Any = 0) -> TrackResult:
        title = _normalize_title(title)
        if not title:
            return TrackResult(ok=False, error="a loop needs a title")
        window = _clamp_window(window_days)
        try:
            result = await self._track(title, window)
        except Exception as exc:
            log.warning("loop_track_failed", error=str(exc))
            return TrackResult(ok=False, error="could not save the loop")
        log.info(
            "loop_tracked", outcome=result.outcome, loop_id=str(result.loop.id)
        )
        return result

    async def _track(self, title: str, window: int) -> TrackResult:
        entity_ids = await resolve_entities(self._resolver, title)
        match = await self._find_match(title, entity_ids)
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(days=window)

        if match is None:
            loop = await self._create(title, entity_ids, now, deadline)
            return TrackResult(ok=True, outcome=TrackOutcome.CREATED, loop=loop)

        if match.state == LoopState.ACTIVE:
            confidence = max(match.confidence, DECLARED_CONFIDENCE)
            await self._store.set_confidence(match.id, confidence)
            match.confidence = confidence
            await self._link_entities(match.id, entity_ids)
            return TrackResult(ok=True, outcome=TrackOutcome.REINFORCED, loop=match)

        revived = match.state == LoopState.DRIFTING
        loop = await self._store.transition(
            match.id, LoopState.ACTIVE.value, user_asked=revived
        )
        await self._stamp(loop, now, deadline)
        await self._link_entities(loop.id, entity_ids)
        outcome = TrackOutcome.REVIVED if revived else TrackOutcome.CONFIRMED
        return TrackResult(ok=True, outcome=outcome, loop=loop)

    async def _find_match(
        self, title: str, entity_ids: list[UUID]
    ) -> OpenLoop | None:
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

    async def _create(
        self, title: str, entity_ids: list[UUID], now: datetime, deadline: datetime
    ) -> OpenLoop:
        loop = OpenLoop(
            title=title,
            claim_kind=LoopClaimKind.PRIORITY,
            provenance=LoopProvenance.USER_DECLARED,
            confidence=DECLARED_CONFIDENCE,
            state=LoopState.ACTIVE,
        )
        created = await submit_and_detect_collisions(
            loop_to_contribution(loop, entity_ids=entity_ids),
            lambda: self._store.create(loop),
            result_id=lambda c: c.id,
            producer_kind="open_loop",
            collision_store=self._collision_store,
            nli_client=self._nli,
        )
        await self._stamp(created, now, deadline)
        await self._link_entities(created.id, entity_ids)
        return created

    async def _stamp(self, loop: OpenLoop, now: datetime, deadline: datetime) -> None:
        await self._store.stamp_declared(
            loop.id, confidence=DECLARED_CONFIDENCE, deadline=deadline
        )
        loop.confidence = DECLARED_CONFIDENCE
        loop.confirmed_at = now
        loop.drift_deadline = deadline
        loop.drift_rationale = None

    async def _link_entities(self, loop_id: UUID, entity_ids: list[UUID]) -> None:
        for entity_id in entity_ids:
            await self._store.link_entity(loop_id, entity_id)
