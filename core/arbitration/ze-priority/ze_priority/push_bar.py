from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import UUID

import numpy as np
from ze_agents.nli import NLIClient
from ze_logging import get_logger
from ze_proactive.candidates import BarThresholds, PushCandidate

log = get_logger(__name__)

BarReason = Literal[
    "low_confidence", "irrelevant", "mentioned_recently", "not_novel", "ungrounded"
]


class PushHistory(Protocol):
    async def recent_discretionary_bodies(self, hours: float) -> list[str]: ...


class MentionRecency(Protocol):
    async def mentioned_inline_within(
        self, source_kind: str, source_id: UUID, hours: float
    ) -> bool: ...


@dataclass(frozen=True)
class BarVerdict:
    candidate: PushCandidate
    passed: bool
    reason: BarReason | None


class PushBar:
    """The one bar every discretionary push passes: confidence, relevance,
    conversation cooldown, novelty against recent pushes, and grounding in
    evidence. A source describes a candidate; it never applies the bar itself."""

    def __init__(
        self,
        *,
        embedder: Any,
        nli: NLIClient | None,
        history: PushHistory,
        mentions: MentionRecency,
        novelty_lookback_hours: float = 48.0,
    ) -> None:
        self._embedder = embedder
        self._nli = nli
        self._history = history
        self._mentions = mentions
        self._novelty_lookback_hours = novelty_lookback_hours
        if nli is None:
            log.warning("push_bar_grounding_off")

    async def screen(
        self, candidates: Sequence[PushCandidate], thresholds: BarThresholds
    ) -> list[BarVerdict]:
        if not candidates:
            return []
        recent = await self._recent_vectors()
        verdicts: list[BarVerdict] = []
        for candidate in candidates:
            reason = await self._first_failure(candidate, thresholds, recent)
            verdicts.append(BarVerdict(candidate, reason is None, reason))
        return verdicts

    async def _first_failure(
        self,
        candidate: PushCandidate,
        thresholds: BarThresholds,
        recent: list[Any],
    ) -> BarReason | None:
        if candidate.confidence < thresholds.confidence:
            return "low_confidence"
        if not await self._relevant(candidate, thresholds):
            return "irrelevant"
        if await self._mentioned(candidate, thresholds):
            return "mentioned_recently"
        if not self._novel(candidate, thresholds, recent):
            return "not_novel"
        if not await self._grounded(candidate, thresholds):
            return "ungrounded"
        return None

    async def _relevant(
        self, candidate: PushCandidate, thresholds: BarThresholds
    ) -> bool:
        # An interruption is not sent on a relevance score that could not be computed.
        try:
            return await candidate.relevance() >= thresholds.relevance
        except Exception as exc:
            log.warning(
                "push_bar_relevance_check_failed",
                source_kind=candidate.source_kind,
                error=str(exc),
            )
            return False

    async def _mentioned(
        self, candidate: PushCandidate, thresholds: BarThresholds
    ) -> bool:
        hours = thresholds.inline_cooldown_hours
        if hours is None:
            return False
        try:
            return await self._mentions.mentioned_inline_within(
                candidate.source_kind, candidate.source_id, hours
            )
        except Exception as exc:
            log.warning(
                "push_bar_mention_check_failed",
                source_kind=candidate.source_kind,
                error=str(exc),
            )
            return False

    async def _recent_vectors(self) -> list[Any]:
        if self._embedder is None:
            return []
        try:
            bodies = await self._history.recent_discretionary_bodies(
                self._novelty_lookback_hours
            )
            return [self._embedder.encode_passage(body) for body in bodies]
        except Exception as exc:
            log.warning("push_bar_novelty_check_failed", error=str(exc))
            return []

    def _novel(
        self, candidate: PushCandidate, thresholds: BarThresholds, recent: list[Any]
    ) -> bool:
        if not recent:
            return True
        try:
            vec = self._embedder.encode_passage(candidate.body)
            for other in recent:
                similarity = float(
                    np.dot(vec, other)
                    / (np.linalg.norm(vec) * np.linalg.norm(other) + 1e-9)
                )
                if similarity > thresholds.novelty_similarity_max:
                    log.info(
                        "push_bar_novelty_failed",
                        similarity=similarity,
                        threshold=thresholds.novelty_similarity_max,
                    )
                    return False
        except Exception as exc:
            log.warning("push_bar_novelty_check_failed", error=str(exc))
        return True

    async def _grounded(
        self, candidate: PushCandidate, thresholds: BarThresholds
    ) -> bool:
        if self._nli is None:
            return True
        try:
            labels = list(await candidate.evidence_labels())
            if not labels:
                return True
            scores = await self._nli.scores(
                [(label, candidate.claim) for label in labels]
            )
            grounded = self._nli.grounding_score(candidate.claim, labels, scores=scores)
            if grounded < thresholds.grounding:
                log.info(
                    "push_bar_grounding_failed",
                    grounded=grounded,
                    threshold=thresholds.grounding,
                )
                return False
        except Exception as exc:
            log.warning("push_bar_grounding_check_failed", error=str(exc))
        return True
