from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from ze_agents.claims import ClaimKind, Provenance
from ze_automation.goals.learning import promote_eligible_learning
from ze_automation.goals.types import (
    GoalLearning,
    LearningEvidence,
    LearningEvidenceKind,
    LearningEvidenceRole,
    LearningPromotion,
    LearningPromotionState,
    LearningStatus,
)
from ze_memory.types import Fact


def _learning(*, user_confirmed: bool = False) -> GoalLearning:
    learning_id = uuid4()
    evidence = []
    if user_confirmed:
        evidence.append(
            LearningEvidence(
                id=uuid4(),
                learning_id=learning_id,
                evidence_kind=LearningEvidenceKind.USER_CONFIRMATION,
                role=LearningEvidenceRole.SUPPORTS,
                excerpt="user approved",
                review_id=uuid4(),
            )
        )
    return GoalLearning(
        id=learning_id,
        goal_id=uuid4(),
        content="I prefer morning study",
        claim_kind=ClaimKind.INFERENCE,
        provenance=Provenance.SYNTHESIZED,
        status=LearningStatus.ACTIVE,
        evidence=evidence,
    )


async def test_active_inference_is_blocked_from_memory_facts() -> None:
    store = AsyncMock()
    store.get_latest_promotion = AsyncMock(return_value=None)
    store.record_promotion = AsyncMock(
        return_value=LearningPromotion(
            learning_id=uuid4(),
            state=LearningPromotionState.BLOCKED,
        )
    )
    memory = AsyncMock()
    with patch(
        "ze_automation.goals.learning.submit_perception_facts",
        new_callable=AsyncMock,
    ) as submit:
        result = await promote_eligible_learning(
            store, _learning(), memory_store=memory
        )
    submit.assert_not_awaited()
    assert result.state is LearningPromotionState.BLOCKED


async def test_user_confirmed_fact_uses_perception_path() -> None:
    store = AsyncMock()
    store.get_latest_promotion = AsyncMock(return_value=None)
    fact_id = uuid4()

    async def _submit(_memory, items):
        items[0].fact.id = fact_id

    store.record_promotion = AsyncMock(
        return_value=LearningPromotion(
            learning_id=uuid4(),
            state=LearningPromotionState.PROMOTED,
            memory_fact_id=fact_id,
        )
    )
    with patch(
        "ze_automation.goals.learning.submit_perception_facts",
        new=_submit,
    ):
        result = await promote_eligible_learning(
            store, _learning(user_confirmed=True), memory_store=AsyncMock()
        )
    assert result.state is LearningPromotionState.PROMOTED
    assert result.memory_fact_id == fact_id
    snapshot = store.record_promotion.await_args.kwargs["snapshot"]
    assert snapshot["permitted_claim_kind"] == ClaimKind.FACT.value
    assert store.record_promotion.await_args.kwargs["memory_fact_id"] == fact_id


async def test_promotion_failure_records_failed_without_partial_claim() -> None:
    store = AsyncMock()
    store.get_latest_promotion = AsyncMock(return_value=None)
    store.record_promotion = AsyncMock(
        return_value=LearningPromotion(
            learning_id=uuid4(),
            state=LearningPromotionState.FAILED,
            failure_reason="boom",
        )
    )

    async def _submit(_memory, items):
        raise RuntimeError("boom")

    with patch(
        "ze_automation.goals.learning.submit_perception_facts",
        new=_submit,
    ):
        result = await promote_eligible_learning(
            store, _learning(user_confirmed=True), memory_store=AsyncMock()
        )
    assert result.state is LearningPromotionState.FAILED
    assert store.record_promotion.await_args.kwargs.get("memory_fact_id") is None


async def test_promoted_fact_is_idempotent() -> None:
    existing = LearningPromotion(
        learning_id=uuid4(),
        state=LearningPromotionState.PROMOTED,
        memory_fact_id=uuid4(),
    )
    store = AsyncMock()
    store.get_latest_promotion = AsyncMock(return_value=existing)
    with patch(
        "ze_automation.goals.learning.submit_perception_facts",
        new_callable=AsyncMock,
    ) as submit:
        result = await promote_eligible_learning(
            store, _learning(user_confirmed=True), memory_store=AsyncMock()
        )
    submit.assert_not_awaited()
    store.record_promotion.assert_not_awaited()
    assert result is existing
    assert isinstance(Fact(predicate="x", value="y"), Fact)
