from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from ze_logging import get_logger

from ze_correlation.engine import CorrelationEngine
from ze_correlation.store import PostgresHypothesisStore
from ze_correlation.types import Hypothesis
from ze_memory.nli_config import nli_config
from ze_correlation.push_kinds import HYPOTHESIS
from ze_proactive.candidates import BarThresholds, PushCandidate
from ze_proactive.types import OncePer, PushOutcome, is_sent

log = get_logger(__name__)

UTC = timezone.utc


class CorrelationPushConsumer:
    """Picks recently admitted signals and correlates them into hypotheses.

    Push-eligibility and sending live in `CorrelationPushCandidateSource` below —
    this consumer no longer self-triggers a push (superseded by
    `AttentionArbitrationJob`, phase 123 User Story 2)."""

    def __init__(
        self,
        engine: CorrelationEngine,
        memory_store: Any,  # PostgresMemoryStore — for seed selection
        settings: Any,
    ) -> None:
        self._engine = engine
        self._memory = memory_store
        self._cfg = _load_config(settings)

    async def run_once(self, *, seeds: list[UUID] | None = None) -> list[Hypothesis]:
        """Correlate recent seeds into persisted hypotheses. Returns all
        hypotheses formed — pushing them is `AttentionArbitrationJob`'s concern."""
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


class CorrelationPushCandidateSource:
    """Hypotheses as push candidates for `AttentionArbitrationJob`. The push bar
    lives in `ze_priority.push_bar`; this class only describes what it would push
    and sends it through the governor."""

    source_kind = "hypothesis"

    def __init__(
        self,
        *,
        hypothesis_store: PostgresHypothesisStore,
        notifier: Any,
        settings: Any,
    ) -> None:
        self._hypothesis_store = hypothesis_store
        self._notifier = notifier
        self._cfg = _load_config(settings)
        self.dry_run: bool = self._cfg.dry_run
        self.thresholds = BarThresholds(
            confidence=self._cfg.tau_push,
            relevance=self._cfg.tau_relevance,
            novelty_similarity_max=self._cfg.novelty_similarity_max,
            grounding=float(
                nli_config(settings).get("nli_grounding_threshold", 0.30)
            ),
            inline_cooldown_hours=None,
        )

    async def candidates(self) -> list[PushCandidate]:
        if not self._cfg.enabled:
            return []
        try:
            hypotheses = await self._hypothesis_store.list_unsurfaced()
        except Exception as exc:
            log.warning("correlation_push_candidates_fetch_failed", error=str(exc))
            return []
        return [self._candidate(h) for h in hypotheses]

    async def send(self, candidate: PushCandidate) -> PushOutcome:
        hypothesis: Hypothesis = candidate.entity
        outcome = await self._notifier.notify(
            HYPOTHESIS,
            "Ze noticed a connection",
            candidate.body,
            target_type="hypothesis",
            target_id=str(hypothesis.id),
            once_per=candidate.once_per,
        )
        if is_sent(outcome):
            await self._hypothesis_store.mark_surfaced(hypothesis.id)
            log.info(
                "correlation_pushed",
                hypothesis_id=str(hypothesis.id),
                outcome=outcome,
            )
        return outcome

    @staticmethod
    def _candidate(hypothesis: Hypothesis) -> PushCandidate:
        async def relevance() -> float:
            return hypothesis.relevance

        async def evidence_labels() -> tuple[str, ...]:
            return tuple(ref.label for ref in hypothesis.evidence if ref.label)

        return PushCandidate(
            source_kind="hypothesis",
            source_id=hypothesis.id,
            entity=hypothesis,
            body=f"{hypothesis.summary}\n\n{hypothesis.narrative}",
            claim=hypothesis.summary,
            confidence=hypothesis.confidence,
            relevance=relevance,
            evidence_labels=evidence_labels,
            once_per=OncePer(f"hypothesis:{hypothesis.id}"),
        )


class _PushConfig:
    __slots__ = (
        "enabled",
        "dry_run",
        "max_seeds_per_run",
        "seed_lookback_hours",
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
    elif isinstance(settings, dict):
        push_cfg = settings.get("correlation", {}).get("push", {})
        surfacing = (
            settings.get("correlation", {}).get("salience", {}).get("surfacing", {})
        )
    else:
        push_cfg = surfacing = {}

    return _PushConfig(
        enabled=bool(push_cfg.get("enabled", False)),
        dry_run=bool(push_cfg.get("dry_run", True)),
        max_seeds_per_run=int(push_cfg.get("max_seeds_per_run", 20)),
        seed_lookback_hours=float(push_cfg.get("seed_lookback_hours", 8.0)),
        tau_push=float(surfacing.get("tau_push", 0.6)),
        tau_relevance=float(surfacing.get("tau_relevance", 0.5)),
        novelty_similarity_max=float(surfacing.get("novelty_similarity_max", 0.85)),
    )
