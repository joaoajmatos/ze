from __future__ import annotations

from typing import Any
from uuid import UUID

from ze_correlation.push import (
    passes_confidence,
    passes_grounding,
    passes_novelty,
    passes_relevance,
)
from ze_logging import get_logger
from ze_memory.graph.store import GraphStore
from ze_proactive.attention_budget import ATTENTION_PUSH_EVENT_KEY
from ze_proactive.types import PushOutcome

from ze_worldstate.push_kinds import LOOP_DRIFT
from ze_worldstate.rest import _fetch_entities, _fetch_evidence_summaries
from ze_worldstate.store import LoopStore
from ze_worldstate.types import LoopState, OpenLoop

log = get_logger(__name__)

_NOVELTY_LOOKBACK_HOURS = 48.0

_DEFAULT_THRESHOLDS = {
    "tau_confidence": 0.5,
    "tau_relevance": 0.5,
    "novelty_similarity_max": 0.85,
    "grounding_threshold": 0.3,
}


def format_hedged_mention(title: str, rationale: str | None) -> str:
    """Hedged inline/push phrasing — never a bare rationale dump (FR-009)."""
    hedge = f'It looks like "{title}" may still be open'
    if rationale:
        return f"{hedge} — {rationale}"
    return f"{hedge}."


class LoopSurfacer:
    def __init__(
        self,
        loop_store: LoopStore,
        graph_store: GraphStore,
        push_log: Any,
        pool: Any = None,
        relevance_model: Any = None,
        embedder: Any = None,
        notifier: Any = None,
        nli_client: Any = None,
    ) -> None:
        self._loop_store = loop_store
        self._graph_store = graph_store
        self._push_log = push_log
        self._pool = pool
        self._notifier = notifier
        self._relevance_model = relevance_model
        self._embedder = embedder
        self._nli_client = nli_client

    async def passes_push_bar(
        self,
        loop: OpenLoop,
        rationale: str,
        *,
        tau_confidence: float = 0.5,
        tau_relevance: float = 0.5,
        novelty_similarity_max: float = 0.85,
        grounding_threshold: float = 0.3,
        inline_cooldown_hours: float = 12.0,
    ) -> bool:
        """Reuses `ze_correlation.push`'s bar functions (FR-007) plus one
        loop-specific gate — the inline-then-push cooldown (FR-012).

        The shared budget is charged by the governor when the push is sent
        (FR-005), not here."""
        if not passes_confidence(loop.confidence, tau_confidence):
            return False

        entity_names = await self._entity_names(loop.id)
        rset = await self._relevance_model.build()
        score = self._relevance_model.score(rset, entity_names, topics=[])
        if not passes_relevance(score.value, tau_relevance):
            return False

        recent_pushes = await self._push_log.list_recent_payloads(
            ATTENTION_PUSH_EVENT_KEY, _NOVELTY_LOOKBACK_HOURS
        )
        if not await passes_novelty(
            format_hedged_mention(loop.title, rationale),
            recent_pushes,
            self._embedder,
            novelty_similarity_max,
        ):
            return False

        evidence_labels = await self._evidence_labels(loop.id)
        if not await passes_grounding(
            loop.title, evidence_labels, self._nli_client, grounding_threshold
        ):
            return False

        already_mentioned = await self._push_log.was_sent_within_hours(
            f"worldstate_loop_inline:{loop.id}", inline_cooldown_hours
        )
        if already_mentioned:
            return False

        return True

    async def eligible_candidates(
        self,
        *,
        thresholds: dict | None = None,
        inline_cooldown_hours: float = 12.0,
    ) -> list[OpenLoop]:
        """Drifting loops that pass every push-bar gate except the shared budget
        claim (novelty/relevance/grounding/idempotency unchanged, SC-004) — for
        `AttentionArbitrationJob` to rank alongside other mechanisms' candidates
        before the first of them is sent (FR-007)."""
        cfg = {**_DEFAULT_THRESHOLDS, **(thresholds or {})}
        loops = await self._loop_store.list([LoopState.DRIFTING.value])
        eligible: list[OpenLoop] = []
        for loop in loops:
            if not loop.drift_rationale:
                continue
            passes = await self.passes_push_bar(
                loop,
                loop.drift_rationale,
                tau_confidence=cfg["tau_confidence"],
                tau_relevance=cfg["tau_relevance"],
                novelty_similarity_max=cfg["novelty_similarity_max"],
                grounding_threshold=cfg["grounding_threshold"],
                inline_cooldown_hours=inline_cooldown_hours,
            )
            if passes:
                eligible.append(loop)
        return eligible

    async def send(self, loop: OpenLoop) -> PushOutcome | None:
        """Send a loop through the governor. Re-checks current lifecycle state
        immediately before sending (FR-011) — the loop may have closed/dropped
        between selection and send. Returns None when it is no longer drifting."""
        current = await self._loop_store.get(loop.id)
        if current is None or current.state != LoopState.DRIFTING:
            return None

        return await self._notifier.notify(
            LOOP_DRIFT,
            "Open loop",
            format_hedged_mention(loop.title, loop.drift_rationale),
            target_type="open_loop",
            target_id=str(loop.id),
            budget_key=f"loop:{loop.id}",
        )

    async def _entity_names(self, loop_id: UUID) -> list[str]:
        if self._pool is None:
            return []
        entities = await _fetch_entities(self._pool, loop_id)
        return [e["canonical_name"] for e in entities]

    async def _evidence_labels(self, loop_id: UUID) -> list[str]:
        summaries = await _fetch_evidence_summaries(
            self._pool, self._loop_store, loop_id
        )
        return [s["summary"] for s in summaries if s.get("summary")]
