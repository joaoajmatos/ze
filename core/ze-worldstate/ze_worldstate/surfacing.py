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
from ze_proactive.attention_budget import release_shared, try_claim_shared, within_budget

from ze_worldstate.matching import _loops_linked_to_entities
from ze_worldstate.rest import _fetch_entities, _fetch_evidence_summaries
from ze_worldstate.store import LoopStore
from ze_worldstate.types import DriftingLoopMention, LoopState, OpenLoop

log = get_logger(__name__)

PUSH_EVENT_KEY = "worldstate_loop_push"
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
    ) -> None:
        self._loop_store = loop_store
        self._graph_store = graph_store
        self._push_log = push_log
        self._pool = pool
        self._relevance_model = relevance_model
        self._embedder = embedder

    async def inline_candidates(self, entity_ids: list[UUID]) -> list[DriftingLoopMention]:
        """Entity-link-overlap matches only — no confidence/relevance/novelty/budget
        gating (FR-006: inline has no such gate)."""
        loops = await _loops_linked_to_entities(
            entity_ids, self._graph_store, self._loop_store
        )
        drifting = [loop for loop in loops if loop.state == LoopState.DRIFTING]

        mentions: list[DriftingLoopMention] = []
        for loop in drifting:
            evidence = await self._loop_store.list_evidence(loop.id)
            mention_text = format_hedged_mention(loop.title, loop.drift_rationale)
            mentions.append(
                DriftingLoopMention(
                    loop_id=loop.id,
                    title=loop.title,
                    mention_text=mention_text,
                    evidence=evidence,
                )
            )
            await self._push_log.log(f"worldstate_loop_inline:{loop.id}")

        return mentions

    async def passes_push_bar(
        self,
        loop: OpenLoop,
        rationale: str,
        *,
        tau_confidence: float = 0.5,
        tau_relevance: float = 0.5,
        novelty_similarity_max: float = 0.85,
        grounding_threshold: float = 0.3,
        max_pushes_per_day: int = 3,
        inline_cooldown_hours: float = 12.0,
        nli_client: Any = None,
        check_budget: bool = True,
    ) -> bool:
        """Reuses `ze_correlation.push`'s bar functions (FR-007) plus one
        loop-specific gate — the inline-then-push cooldown (FR-012).

        `check_budget=False` skips the shared-budget gate — used by
        `eligible_candidates()`, which reports candidates before the budget is
        claimed centrally by `AttentionArbitrationJob` (FR-005)."""
        if not passes_confidence(loop.confidence, tau_confidence):
            return False

        entity_names = await self._entity_names(loop.id)
        rset = await self._relevance_model.build()
        score = self._relevance_model.score(rset, entity_names, topics=[])
        if not passes_relevance(score.value, tau_relevance):
            return False

        recent_summaries = await self._push_log.list_recent_payloads(
            PUSH_EVENT_KEY, _NOVELTY_LOOKBACK_HOURS
        )
        if not await passes_novelty(
            rationale, recent_summaries, self._embedder, novelty_similarity_max
        ):
            return False

        evidence_labels = await self._evidence_labels(loop.id)
        if not await passes_grounding(
            rationale, evidence_labels, nli_client, grounding_threshold
        ):
            return False

        if check_budget and not await within_budget(self._push_log, max_pushes_per_day):
            return False

        already_mentioned = await self._push_log.was_sent_within_hours(
            f"worldstate_loop_inline:{loop.id}", inline_cooldown_hours
        )
        if already_mentioned:
            return False

        return True

    async def claim_push(
        self, loop_id: UUID, rationale: str, max_pushes_per_day: int = 3
    ) -> bool:
        """Claim the shared push slot for this loop. Returns True if this call
        may notify.

        The DB write is the arbiter of exclusivity — two concurrent callers can
        never both win the claim for the same loop_id.
        """
        return await try_claim_shared(
            self._push_log, "loop", loop_id, max_pushes_per_day, payload=rationale
        )

    async def release_push_claim(self, loop_id: UUID) -> None:
        """Roll back a claim whose notification was never delivered."""
        await release_shared(self._push_log, "loop", loop_id)

    async def eligible_candidates(
        self,
        *,
        thresholds: dict | None = None,
        inline_cooldown_hours: float = 12.0,
        nli_client: Any = None,
    ) -> list[OpenLoop]:
        """Drifting loops that pass every push-bar gate except the shared budget
        claim (novelty/relevance/grounding/idempotency unchanged, SC-004) — for
        `AttentionArbitrationJob` to rank alongside other mechanisms' candidates
        before any of them claims the shared budget (FR-007)."""
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
                nli_client=nli_client,
                check_budget=False,
            )
            if passes:
                eligible.append(loop)
        return eligible

    async def send(self, loop: OpenLoop, notifier: Any) -> bool:
        """Send-only path for a loop that has already won the shared-budget
        claim. Re-checks current lifecycle state immediately before sending
        (FR-011) — the loop may have closed/dropped between selection and send."""
        current = await self._loop_store.get(loop.id)
        if current is None or current.state != LoopState.DRIFTING:
            return False

        body = format_hedged_mention(loop.title, loop.drift_rationale)
        await notifier.push(body, urgency="normal")
        return True

    async def _entity_names(self, loop_id: UUID) -> list[str]:
        if self._pool is None:
            return []
        entities = await _fetch_entities(self._pool, loop_id)
        return [e["canonical_name"] for e in entities]

    async def _evidence_labels(self, loop_id: UUID) -> list[str]:
        summaries = await _fetch_evidence_summaries(self._pool, self._loop_store, loop_id)
        return [s["summary"] for s in summaries if s.get("summary")]
