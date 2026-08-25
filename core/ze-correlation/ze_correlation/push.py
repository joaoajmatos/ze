from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import numpy as np

from ze_logging import get_logger

from ze_proactive.attention_budget import release_shared, try_claim_shared

from ze_agents.nli import NLIClient
from ze_correlation.engine import CorrelationEngine
from ze_correlation.store import PostgresHypothesisStore
from ze_correlation.types import Hypothesis
from ze_memory.nli_config import nli_config

log = get_logger(__name__)

UTC = timezone.utc

_NOVELTY_LOOKBACK_HOURS = 48.0


# ── Extracted push-bar primitives (research.md §4) ────────────────────────────
#
# Free functions, parameterized on primitive values instead of `Hypothesis`, so
# both `CorrelationPushConsumer` (below) and `ze_worldstate.surfacing.LoopSurfacer`
# call exactly one implementation of each bar condition (FR-007).


def passes_confidence(confidence: float, tau: float) -> bool:
    return confidence >= tau


def passes_relevance(relevance: float, tau: float) -> bool:
    return relevance >= tau


async def passes_novelty(
    summary: str,
    recent_summaries: list[str],
    embedder: Any,
    max_similarity: float,
) -> bool:
    if embedder is None or not recent_summaries:
        return True
    try:
        new_vec = embedder.encode(summary)
        for other in recent_summaries:
            existing_vec = embedder.encode(other)
            similarity = float(
                np.dot(new_vec, existing_vec)
                / (np.linalg.norm(new_vec) * np.linalg.norm(existing_vec) + 1e-9)
            )
            if similarity > max_similarity:
                log.info(
                    "push_bar_novelty_failed",
                    similarity=similarity,
                    threshold=max_similarity,
                )
                return False
    except Exception as exc:
        log.warning("push_bar_novelty_check_failed", error=str(exc))
    return True


async def passes_grounding(
    summary: str,
    evidence_labels: list[str],
    nli_client: NLIClient | None,
    threshold: float,
) -> bool:
    if nli_client is None or not evidence_labels:
        return True
    try:
        pairs = [(label, summary) for label in evidence_labels]
        scores = await nli_client.scores(pairs)
        grounded = nli_client.grounding_score(summary, evidence_labels, scores=scores)
        if grounded < threshold:
            log.info(
                "push_bar_grounding_failed", grounded=grounded, threshold=threshold
            )
            return False
    except Exception as exc:
        log.warning("push_bar_grounding_check_failed", error=str(exc))
    return True


class CorrelationPushConsumer:
    """Picks recently admitted signals, correlates them, and pushes qualifying hypotheses."""

    def __init__(
        self,
        engine: CorrelationEngine,
        hypothesis_store: PostgresHypothesisStore,
        memory_store: Any,  # PostgresMemoryStore — for seed selection
        notifier: Any,  # ProactiveNotifier
        push_log: Any,  # PushLogStore
        settings: Any,
        embedder: Any = None,  # SentenceTransformer — for novelty gate
        nli_client: NLIClient | None = None,
    ) -> None:
        self._engine = engine
        self._hypothesis_store = hypothesis_store
        self._memory = memory_store
        self._notifier = notifier
        self._push_log = push_log
        self._embedder = embedder
        self._settings = settings
        self._nli = nli_client
        self._cfg = _load_config(settings)

    async def run_once(self, *, seeds: list[UUID] | None = None) -> list[Hypothesis]:
        """Correlate recent seeds and push qualifying hypotheses.

        Returns all hypotheses formed; a subset (those passing the push bar) are pushed.
        """
        if not self._cfg.enabled and not self._cfg.dry_run:
            log.info("correlation_push_disabled")
            return []

        working_seeds = seeds
        if working_seeds is None:
            working_seeds = await self._pick_seeds()

        if not working_seeds:
            log.info("correlation_push_no_seeds")
            return []

        hypotheses = await self._engine.correlate(working_seeds, mode="proactive")
        if not hypotheses:
            log.info("correlation_push_no_hypotheses", seeds=len(working_seeds))
            return hypotheses

        for hypothesis in hypotheses:
            await self._maybe_push(hypothesis)

        return hypotheses

    # ── private ──────────────────────────────────────────────────────────────

    async def _pick_seeds(self) -> list[UUID]:
        since = datetime.now(UTC) - timedelta(hours=self._cfg.seed_lookback_hours)
        try:
            return await self._memory.list_recent_signal_ids(
                since, self._cfg.max_seeds_per_run
            )
        except Exception as exc:
            log.warning("correlation_push_seed_fetch_failed", error=str(exc))
            return []

    async def _maybe_push(self, hypothesis: Hypothesis) -> None:
        if not await self._passes_push_bar(hypothesis):
            log.info(
                "correlation_push_bar_failed",
                hypothesis_id=str(hypothesis.id),
                confidence=hypothesis.confidence,
                relevance=hypothesis.relevance,
            )
            return

        if self._cfg.dry_run:
            log.info(
                "correlation_push_dry_run",
                hypothesis_id=str(hypothesis.id),
                summary=hypothesis.summary,
            )
            return

        claimed = await try_claim_shared(
            self._push_log,
            "hypothesis",
            hypothesis.id,
            self._cfg.max_pushes_per_day,
            payload=str(hypothesis.id),
        )
        if not claimed:
            log.info("correlation_push_budget_exhausted", hypothesis_id=str(hypothesis.id))
            return

        try:
            await self._notifier.push(
                f"Ze noticed a connection:\n\n{hypothesis.summary}\n\n{hypothesis.narrative}",
                urgency="normal",
            )
        except Exception as exc:
            await release_shared(self._push_log, "hypothesis", hypothesis.id)
            log.warning(
                "correlation_push_notify_failed",
                hypothesis_id=str(hypothesis.id),
                error=str(exc),
            )
            return

        await self._hypothesis_store.mark_surfaced(hypothesis.id)
        log.info("correlation_pushed", hypothesis_id=str(hypothesis.id))

    async def _passes_push_bar(self, hypothesis: Hypothesis) -> bool:
        if not passes_confidence(hypothesis.confidence, self._cfg.tau_push):
            return False
        if not passes_relevance(hypothesis.relevance, self._cfg.tau_relevance):
            return False
        if not await self._passes_novelty(hypothesis):
            return False
        if not await self._passes_grounding(hypothesis):
            return False
        return True

    async def _passes_grounding(self, hypothesis: Hypothesis) -> bool:
        labels = [ref.label for ref in hypothesis.evidence if ref.label]
        threshold = float(
            nli_config(self._settings).get("nli_grounding_threshold", 0.30)
        )
        return await passes_grounding(hypothesis.summary, labels, self._nli, threshold)

    async def _passes_novelty(self, hypothesis: Hypothesis) -> bool:
        if self._embedder is None:
            return True
        try:
            recent_summaries = (
                await self._hypothesis_store.list_recently_surfaced_summaries(
                    _NOVELTY_LOOKBACK_HOURS
                )
            )
        except Exception as exc:
            log.warning("correlation_push_novelty_fetch_failed", error=str(exc))
            return True
        return await passes_novelty(
            hypothesis.summary,
            recent_summaries,
            self._embedder,
            self._cfg.novelty_similarity_max,
        )

class _PushConfig:
    __slots__ = (
        "enabled",
        "dry_run",
        "max_seeds_per_run",
        "seed_lookback_hours",
        "max_pushes_per_day",
        "tau_push",
        "tau_relevance",
        "novelty_similarity_max",
    )

    def __init__(self, **kwargs: object) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


def _load_config(settings: Any) -> _PushConfig:
    raw = getattr(settings, "config", None)
    if isinstance(raw, dict):
        push_cfg = raw.get("correlation", {}).get("push", {})
        surfacing = raw.get("correlation", {}).get("salience", {}).get("surfacing", {})
        shared_budget = raw.get("proactive", {}).get("budget", {})
    elif isinstance(settings, dict):
        push_cfg = settings.get("correlation", {}).get("push", {})
        surfacing = (
            settings.get("correlation", {}).get("salience", {}).get("surfacing", {})
        )
        shared_budget = settings.get("proactive", {}).get("budget", {})
    else:
        push_cfg = surfacing = shared_budget = {}

    return _PushConfig(
        enabled=bool(push_cfg.get("enabled", False)),
        dry_run=bool(push_cfg.get("dry_run", True)),
        max_seeds_per_run=int(push_cfg.get("max_seeds_per_run", 20)),
        seed_lookback_hours=float(push_cfg.get("seed_lookback_hours", 8.0)),
        max_pushes_per_day=int(shared_budget.get("max_pushes_per_day", 3)),
        tau_push=float(surfacing.get("tau_push", 0.6)),
        tau_relevance=float(surfacing.get("tau_relevance", 0.5)),
        novelty_similarity_max=float(surfacing.get("novelty_similarity_max", 0.85)),
    )
