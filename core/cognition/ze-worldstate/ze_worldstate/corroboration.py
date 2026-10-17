"""Corroboration — the independence rule and the confidence arithmetic.

Pure policy for phase 172. A text corroborates a suspected loop only when it comes from a source
the loop has not already counted (specs/phases/172-corroboration-promotion/contracts/).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any
from uuid import UUID

from ze_logging import get_logger
from ze_plugin.contribution import EvidenceRef

from ze_worldstate import corroboration_judge
from ze_worldstate.drift import DEFAULT_DRIFT_WINDOW_DAYS
from ze_worldstate.types import (
    LoopSource,
    LoopSourceRole,
    OpenLoop,
    SourceKey,
)

log = get_logger(__name__)

CORROBORATION_WEIGHT = 0.5
CORROBORATED_CAP = 0.6
PROMOTED_CONFIDENCE = 0.7
PROMOTED_WINDOW_DAYS = DEFAULT_DRIFT_WINDOW_DAYS


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
):
    try:
        result = await system_one_client.evaluate(
            corroboration_judge.build_state(existing.title, text, inflow),
            {corroboration_judge.Q_SAME: corroboration_judge.QUESTION},
            max_attempts=1,
        )
    except Exception as exc:
        log.warning("corroboration_system_one_call_failed", error=str(exc))
        return None, corroboration_judge.CorroborationDecision("fallback", "error")
    decision = corroboration_judge.decide(result, cfg)
    if decision.reason == "invalid_answer":
        log.warning("corroboration_invalid_answer")
    return result, decision


async def corroborate_match(
    *,
    existing: OpenLoop,
    text: str,
    inflow: str,
    key: SourceKey | None,
    evidence_refs: Sequence[EvidenceRef],
    entity_ids: Sequence[UUID],
    dropped: OpenLoop | None,
    loop_store: Any,
    system_one_client: Any,
    settings: Any,
    link: Callable[[], Awaitable[None]],
) -> None:
    """A gate-admitted text matched a suspected loop. Never raises.

    `link` is the 170 evidence-and-entity link; it runs on every path, after independence is
    checked (linking first would make every text look like the same evidence).
    """
    try:
        await _corroborate(
            existing=existing,
            text=text,
            inflow=inflow,
            key=key,
            evidence_refs=evidence_refs,
            dropped=dropped,
            loop_store=loop_store,
            system_one_client=system_one_client,
            settings=settings,
            link=link,
        )
    except Exception as exc:
        log.warning(
            "corroboration_failed", loop_id=str(existing.id), inflow=inflow, error=str(exc)
        )
        try:
            await link()
        except Exception as link_exc:
            log.warning("corroboration_link_failed", error=str(link_exc))


async def _corroborate(
    *,
    existing: OpenLoop,
    text: str,
    inflow: str,
    key: SourceKey | None,
    evidence_refs: Sequence[EvidenceRef],
    dropped: OpenLoop | None,
    loop_store: Any,
    system_one_client: Any,
    settings: Any,
    link: Callable[[], Awaitable[None]],
) -> None:
    cfg = corroboration_judge.corroboration_surface_config(settings)
    if not cfg.enabled:
        await link()
        return
    if not cfg.calibrated:
        log.warning("corroboration_uncalibrated")
        await link()
        return
    if system_one_client is None:
        await link()
        return

    loop_sources = await loop_store.list_sources(existing.id)
    loop_evidence = await loop_store.list_evidence(existing.id)
    dropped_sources = await loop_store.list_sources(dropped.id) if dropped else []
    independent, reason = is_independent(
        key, evidence_refs, loop_sources, loop_evidence, dropped_sources
    )
    if not independent:
        log.debug(
            "corroboration_skipped",
            loop_id=str(existing.id),
            inflow=inflow,
            reason=reason,
        )
        await link()
        return

    result, decision = await _judge(existing, text, inflow, system_one_client, cfg)
    outcome, reason = decision.kind, decision.reason
    if decision.kind in ("promote", "corroborate"):
        await link()
        row = await loop_store.add_source(
            LoopSource(
                loop_id=existing.id,
                role=LoopSourceRole.CORROBORATION,
                key=key,
                evidence=evidence_refs[0] if evidence_refs else None,
                same_concern=decision.score,
                model=result.model,
                latency_ms=result.latency_ms,
            )
        )
        if row is None:
            outcome, reason = "corroborate", "duplicate_source"
        else:
            corroborated = corroborated_confidence(
                existing.confidence, decision.score
            )
            outcome = "corroborate"
            promoted = None
            if decision.kind == "promote":
                # Promote writes confidence itself (0.7 is above the corroboration
                # cap), so the stamped prior is the value before this one write.
                promoted = await loop_store.promote(
                    existing.id,
                    confidence=PROMOTED_CONFIDENCE,
                    window_days=PROMOTED_WINDOW_DAYS,
                )
            if promoted is not None:
                await loop_store.mark_source_promoted(row.id)
                outcome = "promote"
            else:
                await loop_store.set_confidence(existing.id, corroborated)
    else:
        await link()

    log.info(
        "corroboration_judgment",
        loop_id=str(existing.id),
        inflow=inflow,
        outcome=outcome,
        reason=reason,
        score=decision.score,
        latency_ms=result.latency_ms if result else None,
        skip_reason=decision.reason if decision.kind == "fallback" else None,
    )
