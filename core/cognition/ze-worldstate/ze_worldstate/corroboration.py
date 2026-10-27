"""Corroboration — the independence rule, the confidence arithmetic and the match flow.

A text corroborates a suspected loop only when it comes from a source the loop has not already
counted (specs/phases/172-corroboration-promotion/contracts/). `Corroborator` judges a match and
hands the effect to the lifecycle: one call per path.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ze_agents.judgment import Judgment, gate, judge
from ze_logging import get_logger
from ze_plugin.contribution import EvidenceRef

from ze_worldstate import corroboration_judge
from ze_worldstate.lifecycle import Corroboration, DeclaredStamp, SourceWrite
from ze_worldstate.types import LoopSource, OpenLoop, SourceKey

log = get_logger(__name__)

CORROBORATION_WEIGHT = 0.5
CORROBORATED_CAP = 0.6
PROMOTED_WINDOW_DAYS = DeclaredStamp.DEFAULT_WINDOW_DAYS


def is_independent(
    key: SourceKey | None,
    new_evidence: Sequence[EvidenceRef],
    loop_sources: Sequence[LoopSource],
    loop_evidence: Sequence[EvidenceRef],
    dropped_sources: Sequence[LoopSource],
) -> tuple[bool, str]:
    """Pure. Returns (independent, reason); the reason is only for the log."""
    if key is None or not key.ref:
        return False, "no_key"
    if key in {s.key for s in loop_sources}:
        return False, "same_source"
    known = {(e.kind, e.id) for e in loop_evidence}
    if any((e.kind, e.id) in known for e in new_evidence):
        return False, "same_evidence"
    if key in {s.key for s in dropped_sources}:
        return False, "dropped_source"
    return True, "independent"


def corroborated_confidence(confidence: float, score: float) -> float:
    """Noisy-OR with the score as a weight, capped below the promoted level."""
    raised = 1 - (1 - confidence) * (1 - CORROBORATION_WEIGHT * score)
    return min(CORROBORATED_CAP, max(confidence, raised))


async def _judge(
    existing: OpenLoop,
    text: str,
    inflow: str,
    system_one_client: Any,
    cfg: corroboration_judge.CorroborationSurfaceConfig,
) -> tuple[Judgment, corroboration_judge.CorroborationDecision]:
    judgment, decision = await judge(
        system_one_client,
        cfg,
        corroboration_judge.build_state(existing.title, text, inflow),
        {corroboration_judge.Q_SAME: corroboration_judge.QUESTION},
        lambda result: corroboration_judge.decide(result, cfg),
        corroboration_judge.read_decision,
    )
    if decision.reason == "invalid_answer":
        log.warning("corroboration_invalid_answer")
    return judgment, decision


@dataclass(frozen=True)
class MatchInput:
    text: str
    inflow: str
    key: SourceKey | None
    evidence: tuple[EvidenceRef, ...]
    entity_ids: tuple[UUID, ...]


class Corroborator:
    def __init__(
        self,
        *,
        lifecycle: Any,
        loop_store: Any,
        system_one_client: Any = None,
        settings: Any = None,
    ) -> None:
        self._lifecycle = lifecycle
        self._loop_store = loop_store
        self._system_one = system_one_client
        self._settings = settings

    async def on_suspected_match(
        self, existing: OpenLoop, dropped: OpenLoop | None, match: MatchInput
    ) -> SourceWrite | OpenLoop:
        """A gate-admitted text matched a suspected loop.

        Judging never raises: any failure there falls back to `note_evidence`, which runs on
        every path that does not corroborate, after independence is checked (linking first would
        make every text look like the same evidence).
        """
        try:
            written = await self._corroborate(existing, dropped, match)
        except Exception as exc:
            log.warning(
                "corroboration_failed",
                loop_id=str(existing.id),
                inflow=match.inflow,
                error=str(exc),
            )
            written = None
        if written is not None:
            return written
        return await self._lifecycle.note_evidence(
            existing.id, evidence=match.evidence, entity_ids=match.entity_ids
        )

    async def _corroborate(
        self, existing: OpenLoop, dropped: OpenLoop | None, match: MatchInput
    ) -> SourceWrite | None:
        cfg = corroboration_judge.CorroborationSurfaceConfig.from_settings(
            self._settings
        )
        if gate(cfg, self._system_one) is not None:
            return None

        loop_sources = await self._loop_store.list_sources(existing.id)
        loop_evidence = await self._loop_store.list_evidence(existing.id)
        dropped_sources = (
            await self._loop_store.list_sources(dropped.id) if dropped else []
        )
        independent, reason = is_independent(
            match.key, match.evidence, loop_sources, loop_evidence, dropped_sources
        )
        if not independent or match.key is None:
            log.debug(
                "corroboration_skipped",
                loop_id=str(existing.id),
                inflow=match.inflow,
                reason=reason,
            )
            return None

        judgment, decision = await _judge(
            existing, match.text, match.inflow, self._system_one, cfg
        )
        result = judgment.result
        written: SourceWrite | None = None
        outcome = decision.kind
        if decision.kind in ("promote", "corroborate"):
            score = decision.score or 0.0
            corroboration = Corroboration(
                evidence=match.evidence,
                entity_ids=match.entity_ids,
                key=match.key,
                same_concern=score,
                confidence=corroborated_confidence(existing.confidence, score),
                model=result.model,
                latency_ms=result.latency_ms,
            )
            if decision.kind == "promote":
                written = await self._lifecycle.promote(existing.id, corroboration)
            else:
                written = await self._lifecycle.corroborate(existing.id, corroboration)
            outcome = written.outcome

        log.info(
            "corroboration_judgment",
            loop_id=str(existing.id),
            inflow=match.inflow,
            outcome=outcome,
            reason=decision.reason,
            score=decision.score,
            latency_ms=result.latency_ms,
            skip_reason=judgment.skip_reason,
        )
        return written
