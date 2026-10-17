from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from ze_agents.claims import ClaimKind
from ze_logging import get_logger

from ze_correlation.store import DisplayState, Feedback, PostgresHypothesisStore
from ze_correlation.types import Hypothesis

log = get_logger(__name__)

EntityNames = Callable[[list[UUID]], Awaitable[dict[UUID, str]]]

_ALLOWED_KINDS = {ClaimKind.INFERENCE, ClaimKind.SUSPICION}


def _item(h: Hypothesis, names: dict[UUID, str]) -> dict:
    return {
        "id": h.id,
        "summary": h.summary,
        "narrative": h.narrative,
        "relation": h.relation,
        "confidence": h.confidence,
        "claim_kind": h.claim_kind.value,
        "evidence": [
            {"kind": e.kind, "id": e.id, "label": e.label} for e in h.evidence
        ],
        "entities": [{"id": e, "name": names.get(e)} for e in h.entities],
        "surfaced": h.surfaced,
        "feedback": h.feedback,
        "confirmed": h.confirmed,
        "created_at": h.created_at.isoformat(),
    }


async def list_hypotheses(
    store: PostgresHypothesisStore,
    entity_names: EntityNames,
    *,
    entity_id: UUID | None,
    state: DisplayState,
    limit: int,
) -> list[dict]:
    rows = await store.list_for_display(entity_id=entity_id, state=state, limit=limit)
    kept: list[Hypothesis] = []
    for h in rows:
        if h.claim_kind not in _ALLOWED_KINDS:
            log.error(
                "hypothesis_claim_kind_invalid",
                hypothesis_id=str(h.id),
                claim_kind=h.claim_kind.value,
            )
            continue
        kept.append(h)
    ids = list({e for h in kept for e in h.entities})
    names = await entity_names(ids) if ids else {}
    return [_item(h, names) for h in kept]


async def set_feedback(
    store: PostgresHypothesisStore,
    entity_names: EntityNames,
    hypothesis_id: UUID,
    feedback: Feedback | None,
) -> dict:
    h = await store.set_feedback(hypothesis_id, feedback)
    names = await entity_names(list(h.entities)) if h.entities else {}
    return _item(h, names)
