from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

from ze_logging import get_logger
from ze_memory.graph.store import GraphStore
from ze_proactive.candidates import BarThresholds, PushCandidate
from ze_proactive.types import OncePer, PushOutcome

from ze_worldstate.push_kinds import LOOP_DRIFT
from ze_worldstate.rest import _fetch_entities, _fetch_evidence_summaries
from ze_worldstate.store import LoopStore
from ze_worldstate.types import LoopState

if TYPE_CHECKING:
    from ze_worldstate.bootstrap import LoopPushSettings

log = get_logger(__name__)


def format_hedged_mention(title: str, rationale: str | None) -> str:
    """Hedged inline/push phrasing — never a bare rationale dump (FR-009)."""
    hedge = f'It looks like "{title}" may still be open'
    if rationale:
        return f"{hedge} — {rationale}"
    return f"{hedge}."


class LoopSurfacer:
    """Drifting loops as push candidates for `AttentionArbitrationJob`. The push
    bar lives in `ze_priority.push_bar`; this class only describes what it would
    push and sends it through the governor."""

    source_kind = "loop"
    dry_run = False

    def __init__(
        self,
        *,
        loop_store: LoopStore,
        graph_store: GraphStore,
        pool: Any,
        relevance_model: Any,
        notifier: Any,
        settings: LoopPushSettings,
    ) -> None:
        self._loop_store = loop_store
        self._graph_store = graph_store
        self._pool = pool
        self._relevance_model = relevance_model
        self._notifier = notifier
        self._settings = settings

    @property
    def thresholds(self) -> BarThresholds:
        return self._settings.bar_thresholds()

    async def candidates(self) -> list[PushCandidate]:
        loops = await self._loop_store.list([LoopState.DRIFTING.value])
        within = timedelta(days=self._settings.repush_after_days)
        return [
            PushCandidate(
                source_kind=self.source_kind,
                source_id=loop.id,
                entity=loop,
                body=format_hedged_mention(loop.title, loop.drift_rationale),
                claim=loop.title,
                confidence=loop.confidence,
                relevance=self._relevance_thunk(loop.id),
                evidence_labels=self._evidence_thunk(loop.id),
                once_per=OncePer(f"loop:{loop.id}", within=within),
            )
            for loop in loops
            if loop.drift_rationale
        ]

    async def send(self, candidate: PushCandidate) -> PushOutcome | None:
        """Re-checks the lifecycle state immediately before sending (FR-011): the
        loop may have closed or dropped since selection. None when it is no longer
        drifting."""
        current = await self._loop_store.get(candidate.source_id)
        if current is None or current.state != LoopState.DRIFTING:
            return None

        return await self._notifier.notify(
            LOOP_DRIFT,
            "Open loop",
            candidate.body,
            target_type="open_loop",
            target_id=str(candidate.source_id),
            once_per=candidate.once_per,
        )

    def _relevance_thunk(self, loop_id: UUID):
        async def relevance() -> float:
            entity_names = await self._entity_names(loop_id)
            rset = await self._relevance_model.build()
            return self._relevance_model.score(rset, entity_names, topics=[]).value

        return relevance

    def _evidence_thunk(self, loop_id: UUID):
        async def evidence_labels() -> tuple[str, ...]:
            summaries = await _fetch_evidence_summaries(
                self._pool, self._loop_store, loop_id
            )
            return tuple(s["summary"] for s in summaries if s.get("summary"))

        return evidence_labels

    async def _entity_names(self, loop_id: UUID) -> list[str]:
        if self._pool is None:
            return []
        entities = await _fetch_entities(self._pool, loop_id)
        return [e["canonical_name"] for e in entities]
