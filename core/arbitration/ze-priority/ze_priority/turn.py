"""Turn surfacing for open items (loops, goals, workflows).

Memory facts are not mention chips. Retrieved biography is injected into the
system prompt; unsolicited fact recitation is forbidden. Do not extend this
module to dump preference/identity facts as inline mentions.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import UUID

from ze_logging import get_logger
from ze_priority.errors import ZePriorityError
from ze_priority.merge import merge
from ze_priority.store import PriorityOverrideStore
from ze_priority.types import (
    LoopSignal,
    MergedPriorityItem,
    OpenItemMention,
    PriorityItem,
    RelationshipSignal,
)
from ze_priority.view import PriorityView
from ze_worldstate.matching import _loops_linked_to_entities
from ze_worldstate.surfacing import format_hedged_mention

log = get_logger(__name__)

UTC = timezone.utc

INLINE_MENTION_LIMIT = 3

_GLOBAL_OPEN_RE = re.compile(
    r"\b("
    r"what(?:'s|s| is) open"
    r"|what(?:'s|s| is) outstanding"
    r"|what(?:'s|s| is) on my plate"
    r")\b",
    re.IGNORECASE,
)

_MIN_NAME_LEN = 3


class TurnSurfacing:
    """Conversation-turn consumer of the merged PriorityView snapshot."""

    def __init__(
        self,
        priority_view: PriorityView,
        override_store: PriorityOverrideStore | None,
        graph_store: Any,
        loop_store: Any,
        push_log: Any | None = None,
    ) -> None:
        self._priority_view = priority_view
        self._override_store = override_store
        self._graph_store = graph_store
        self._loop_store = loop_store
        self._push_log = push_log

    @staticmethod
    def is_global_open_query(prompt: str) -> bool:
        return bool(_GLOBAL_OPEN_RE.search(prompt or ""))

    async def recap_mentions(self) -> list[OpenItemMention]:
        snapshot = await self._snapshot()
        if snapshot is None:
            return []
        merged, items_by_id = snapshot
        return [
            self._format_mention(items_by_id[row.source_id])
            for row in merged
            if row.source_id in items_by_id
        ]

    async def inline_mentions(
        self,
        entity_ids: list[UUID],
        *,
        entities: Sequence[Any] = (),
    ) -> list[OpenItemMention]:
        if not entity_ids:
            return []
        snapshot = await self._snapshot()
        if snapshot is None:
            return []
        merged, items_by_id = snapshot
        relevant_loop_ids = await self._relevant_loop_ids(entity_ids)
        names = _entity_names(entities)
        selected: list[OpenItemMention] = []
        for row in merged:
            item = items_by_id.get(row.source_id)
            if item is None:
                continue
            if not _is_relevant(item, entity_ids, relevant_loop_ids, names):
                continue
            mention = self._format_mention(item)
            selected.append(mention)
            if len(selected) >= INLINE_MENTION_LIMIT:
                break
        await self._log_loop_inlines(selected)
        return selected

    async def _snapshot(
        self,
    ) -> tuple[list[MergedPriorityItem], dict[UUID, PriorityItem]] | None:
        try:
            ranking = await self._priority_view.rank()
        except ZePriorityError as exc:
            log.warning("turn_surfacing_rank_failed", error=str(exc))
            return None
        except Exception as exc:
            log.warning("turn_surfacing_rank_failed", error=str(exc))
            return None

        items_by_id = {item.source_id: item for item in ranking.items}
        overrides: list = []
        if self._override_store is not None:
            try:
                overrides = await self._override_store.get_active()
            except Exception as exc:
                log.warning("turn_surfacing_override_store_failed", error=str(exc))

        merged = merge(ranking, overrides, datetime.now(UTC))
        return merged, items_by_id

    async def _relevant_loop_ids(self, entity_ids: list[UUID]) -> set[UUID]:
        try:
            loops = await _loops_linked_to_entities(
                entity_ids, self._graph_store, self._loop_store
            )
        except Exception as exc:
            log.warning("turn_surfacing_loop_overlap_failed", error=str(exc))
            return set()
        return {loop.id for loop in loops if loop.id is not None}

    async def _log_loop_inlines(self, mentions: list[OpenItemMention]) -> None:
        if self._push_log is None:
            return
        for mention in mentions:
            if mention.source_kind != "loop":
                continue
            try:
                await self._push_log.log(f"worldstate_loop_inline:{mention.source_id}")
            except Exception as exc:
                log.warning("turn_surfacing_inline_log_failed", error=str(exc))

    def _format_mention(self, item: PriorityItem) -> OpenItemMention:
        detail: str | None = None
        if isinstance(item.signal, LoopSignal):
            detail = item.signal.drift_rationale
        elif isinstance(item.signal, RelationshipSignal):
            detail = f"no contact in {item.signal.days_ago} days"
        return OpenItemMention(
            source_kind=item.source_kind,
            source_id=item.source_id,
            title=item.title,
            mention_text=format_hedged_mention(item.title, detail),
        )


def _entity_names(entities: Sequence[Any]) -> list[str]:
    names: list[str] = []
    for entity in entities:
        canonical = getattr(entity, "canonical_name", None)
        if canonical:
            names.append(str(canonical))
        for alias in getattr(entity, "aliases", None) or []:
            names.append(str(alias))
    return names


def _is_relevant(
    item: PriorityItem,
    entity_ids: list[UUID],
    relevant_loop_ids: set[UUID],
    names: list[str],
) -> bool:
    if item.source_kind == "loop":
        return item.source_id in relevant_loop_ids
    if item.source_kind == "hypothesis":
        return bool(set(item.linked_entity_ids) & set(entity_ids))
    return _text_matches(item.match_text, names)


def _text_matches(match_text: str, names: list[str]) -> bool:
    haystack = match_text.casefold()
    if not haystack:
        return False
    for name in names:
        needle = name.casefold().strip()
        if len(needle) < _MIN_NAME_LEN:
            continue
        if needle in haystack:
            return True
    return False
