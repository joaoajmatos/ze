"""Turn surfacing for open items (loops, goals, workflows).

Memory facts are not mention chips. Retrieved biography is injected into the
system prompt; unsolicited fact recitation is forbidden. Do not extend this
module to dump preference/identity facts as inline mentions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import UUID

from ze_components.serialize import serialize_primitive
from ze_logging import get_logger
from ze_priority.compose.rules import mention_card
from ze_priority.errors import ZePriorityError
from ze_priority.open_query import OpenQueryDetector
from ze_priority.types import (
    LoopOffer,
    LoopSignal,
    OpenItemMention,
    PriorityItem,
    RelationshipSignal,
)
from ze_priority.view import PriorityView
from ze_worldstate.matching import _loops_linked_to_entities
from ze_worldstate.surfacing import format_hedged_mention
from ze_worldstate.types import LoopState

log = get_logger(__name__)

UTC = timezone.utc

INLINE_MENTION_LIMIT = 3
OFFER_LIMIT = 3
OFFER_COOLDOWN_HOURS = 168
RECAP_LIMIT = 5
OPEN_QUERY_LIMIT = 10
OFFER_EVENT_PREFIX = "worldstate_loop_offer:"

_MIN_NAME_LEN = 3


class TurnSurfacing:
    """Conversation-turn consumer of the merged PriorityView snapshot."""

    def __init__(
        self,
        priority_view: PriorityView,
        graph_store: Any,
        loop_store: Any,
        embedder: Any,
        push_log: Any | None = None,
        open_query_detector: OpenQueryDetector | None = None,
    ) -> None:
        self._priority_view = priority_view
        self._graph_store = graph_store
        self._loop_store = loop_store
        self._push_log = push_log
        self._open_query = open_query_detector or OpenQueryDetector(embedder)

    def is_global_open_query(self, embedding: Any) -> bool:
        return self._open_query.is_open_query(embedding)

    async def recap_mentions(self, limit: int | None = None) -> list[OpenItemMention]:
        items = await self._snapshot()
        if items is None:
            return []
        mentions = [self._format_mention(item) for item in items]
        return mentions if limit is None else mentions[:limit]

    async def open_query_mentions(self, limit: int) -> list[OpenItemMention]:
        """Ranked items, then suspected loops labeled unconfirmed, for "what's open?".

        Suspected loops are not ranked or pushed; they only appear in this answer.
        """
        mentions = await self.recap_mentions(limit=limit)
        room = limit - len(mentions)
        if room <= 0:
            return mentions
        try:
            loops = await self._loop_store.list(states=[LoopState.SUSPECTED.value])
        except Exception as exc:
            log.warning("turn_surfacing_suspected_list_failed", error=str(exc))
            return mentions
        suspected = sorted(
            (loop for loop in loops if loop.id is not None),
            key=lambda loop: (
                -loop.confidence,
                -(loop.created_at.timestamp() if loop.created_at else 0.0),
            ),
        )
        for loop in suspected[:room]:
            mentions.append(
                OpenItemMention(
                    source_kind="loop",
                    source_id=loop.id,
                    title=loop.title,
                    mention_text=f'"{loop.title}" (unconfirmed — not tracked yet)',
                )
            )
        return mentions

    async def resume_loop_offers(self, limit: int = OFFER_LIMIT) -> list[LoopOffer]:
        """Suspected loops to ask about at session resume, recorded as offered.

        Without a push log there is no cooldown record, so nothing is offered.
        """
        if self._push_log is None:
            return []
        try:
            loops = await self._loop_store.list(states=[LoopState.SUSPECTED.value])
        except Exception as exc:
            log.warning("turn_surfacing_offer_list_failed", error=str(exc))
            return []
        candidates = sorted(
            (loop for loop in loops if loop.id is not None),
            key=lambda loop: (
                -loop.confidence,
                -(loop.created_at.timestamp() if loop.created_at else 0.0),
            ),
        )
        offers: list[LoopOffer] = []
        for loop in candidates:
            if len(offers) == limit:
                break
            try:
                cooling = await self._push_log.was_sent_within_hours(
                    f"{OFFER_EVENT_PREFIX}{loop.id}", OFFER_COOLDOWN_HOURS
                )
            except Exception as exc:
                log.warning("turn_surfacing_offer_cooldown_failed", error=str(exc))
                return []
            if not cooling:
                offers.append(LoopOffer(loop.id, loop.title, loop.provenance))
        for offer in offers:
            try:
                await self._push_log.log(f"{OFFER_EVENT_PREFIX}{offer.loop_id}")
            except Exception as exc:
                log.warning("turn_surfacing_offer_log_failed", error=str(exc))
        return offers

    async def inline_mentions(
        self,
        entity_ids: list[UUID],
        *,
        entities: Sequence[Any] = (),
    ) -> list[OpenItemMention]:
        if not entity_ids:
            return []
        items = await self._snapshot()
        if items is None:
            return []
        relevant_loop_ids = await self._relevant_loop_ids(entity_ids)
        names = _entity_names(entities)
        selected: list[OpenItemMention] = []
        for item in items:
            if not _is_relevant(item, entity_ids, relevant_loop_ids, names):
                continue
            mention = self._format_mention(item)
            selected.append(mention)
            if len(selected) >= INLINE_MENTION_LIMIT:
                break
        await self._log_loop_inlines(selected)
        return selected

    async def mention_cards(self, mentions: Sequence[OpenItemMention]) -> list[dict]:
        """One serialized claim card per mention, posture read from its record."""
        now = datetime.now(UTC)
        cards: list[dict] = []
        for mention in mentions:
            loop = None
            if mention.source_kind == "loop":
                try:
                    loop = await self._loop_store.get(mention.source_id)
                except Exception as exc:
                    log.warning("turn_surfacing_card_loop_failed", error=str(exc))
            card = mention_card(mention.item, now, loop=loop)
            if card is not None:
                cards.append(serialize_primitive(card))
        return cards

    async def _snapshot(
        self,
    ) -> list[PriorityItem] | None:
        try:
            ranking = await self._priority_view.rank()
        except ZePriorityError as exc:
            log.warning("turn_surfacing_rank_failed", error=str(exc))
            return None
        except Exception as exc:
            log.warning("turn_surfacing_rank_failed", error=str(exc))
            return None

        return ranking.items

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
            item=item,
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
