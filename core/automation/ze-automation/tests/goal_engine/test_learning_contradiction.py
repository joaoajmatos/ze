from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

from ze_agents.claims import ClaimKind, Provenance
from ze_automation.goals.learning import apply_nli_contradictions
from ze_automation.goals.types import (
    GoalLearning,
    GoalLearningSummary,
    LearningEvidence,
    LearningEvidenceKind,
    LearningEvidenceRole,
    LearningPromotionState,
    LearningStatus,
)


async def test_nli_contradiction_queues_review_without_arbitration():
    existing_id = uuid4()
    action_id = uuid4()
    new_learning = GoalLearning(
        id=uuid4(),
        goal_id=uuid4(),
        content="evening study is better",
        claim_kind=ClaimKind.INFERENCE,
        provenance=Provenance.SYNTHESIZED,
        evidence=[
            LearningEvidence(
                id=uuid4(),
                learning_id=uuid4(),
                evidence_kind=LearningEvidenceKind.ACTION_RECORD,
                role=LearningEvidenceRole.SUPPORTS,
                excerpt="trace",
                action_record_id=action_id,
            )
        ],
    )
    store = AsyncMock()
    store.list_goal_learnings = AsyncMock(
        return_value=[
            GoalLearningSummary(
                id=existing_id,
                content="morning study is better",
                claim_kind=ClaimKind.INFERENCE,
                provenance=Provenance.SYNTHESIZED,
                confidence=0.4,
                status=LearningStatus.ACTIVE,
                evidence_count=1,
                promotion_state=None,
                review_needed=False,
            )
        ]
    )
    nli = AsyncMock()
    nli.scores = AsyncMock(
        return_value=[{"contradiction": 0.9, "neutral": 0.05, "entailment": 0.05}]
    )
    await apply_nli_contradictions(store, nli, new_learning)
    store.record_contradiction.assert_awaited_once()
    args = store.record_contradiction.await_args
    assert args.args[0] == existing_id
    assert args.kwargs["rationale"] == "nli contradiction"
    assert args.args[1].role.value == "contradicts"


async def test_weak_nli_score_does_not_choose_a_winner():
    store = AsyncMock()
    store.list_goal_learnings = AsyncMock(
        return_value=[
            GoalLearningSummary(
                id=uuid4(),
                content="morning study is better",
                claim_kind=ClaimKind.INFERENCE,
                provenance=Provenance.SYNTHESIZED,
                confidence=0.4,
                status=LearningStatus.ACTIVE,
                evidence_count=1,
                promotion_state=LearningPromotionState.BLOCKED,
                review_needed=False,
            )
        ]
    )
    nli = AsyncMock()
    nli.scores = AsyncMock(
        return_value=[{"contradiction": 0.1, "neutral": 0.8, "entailment": 0.1}]
    )
    learning = GoalLearning(
        id=uuid4(),
        goal_id=uuid4(),
        content="evening study is better",
        evidence=[
            LearningEvidence(
                id=uuid4(),
                learning_id=uuid4(),
                evidence_kind=LearningEvidenceKind.ACTION_RECORD,
                role=LearningEvidenceRole.SUPPORTS,
                excerpt="trace",
                action_record_id=uuid4(),
            )
        ],
    )
    await apply_nli_contradictions(store, nli, learning)
    store.record_contradiction.assert_not_awaited()
