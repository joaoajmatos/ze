from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ze_api.api.deps import get_entity_names, get_hypothesis_store, require_api_key
from ze_api.api.v0.hypotheses.schemas import HypothesisFeedbackRequest, HypothesisItem
from ze_correlation import rest as hypothesis_rest
from ze_correlation.store import HypothesisNotFoundError

router = APIRouter(
    prefix="/hypotheses",
    tags=["hypotheses"],
    dependencies=[Depends(require_api_key)],
)


@router.get(
    "",
    response_model=list[HypothesisItem],
    operation_id="listHypotheses",
    summary="List correlation hypotheses",
    description=(
        "Hypotheses Ze has formed from cross-domain evidence, newest first, each with "
        "confidence, relation, evidence and the entities it concerns. state is open "
        "(not confirmed and not dismissed), confirmed, dismissed (marked not_relevant "
        "or muted) or all. claim_kind is inference or suspicion, never fact."
    ),
)
async def list_hypotheses(
    entity_id: UUID | None = Query(default=None, description="Only hypotheses about this entity."),
    state: Literal["open", "confirmed", "dismissed", "all"] = "open",
    limit: int = Query(default=50),
    store=Depends(get_hypothesis_store),
    entity_names=Depends(get_entity_names),
) -> list[HypothesisItem]:
    limit = max(1, min(limit, 200))
    rows = await hypothesis_rest.list_hypotheses(
        store, entity_names, entity_id=entity_id, state=state, limit=limit
    )
    return [HypothesisItem.model_validate(r) for r in rows]


@router.post(
    "/{hypothesis_id}/feedback",
    response_model=HypothesisItem,
    operation_id="setHypothesisFeedback",
    summary="Record feedback on a hypothesis",
    description=(
        "Record useful, not_relevant or muted. A not_relevant or muted hypothesis is "
        "no longer pushed, ranked or offered in conversation. Send null to clear the "
        "feedback, which undoes a dismissal."
    ),
)
async def set_hypothesis_feedback(
    hypothesis_id: UUID,
    body: HypothesisFeedbackRequest,
    store=Depends(get_hypothesis_store),
    entity_names=Depends(get_entity_names),
) -> HypothesisItem:
    try:
        row = await hypothesis_rest.set_feedback(
            store, entity_names, hypothesis_id, body.feedback
        )
    except HypothesisNotFoundError:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    return HypothesisItem.model_validate(row)
