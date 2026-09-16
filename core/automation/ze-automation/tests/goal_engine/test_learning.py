from __future__ import annotations

from uuid import uuid4

from ze_agents.claims import ClaimKind
from ze_automation.goals.learning import evaluate_eligibility
from ze_automation.goals.types import (
    GoalLearning,
    LearningEvidenceDraft,
    LearningEvidenceKind,
    LearningEvidenceRole,
    LearningStatus,
)


def _action(*, context: str, action_id=None) -> LearningEvidenceDraft:
    return LearningEvidenceDraft(
        evidence_kind=LearningEvidenceKind.ACTION_RECORD,
        role=LearningEvidenceRole.SUPPORTS,
        excerpt="verified outcome",
        action_record_id=action_id or uuid4(),
        execution_context_key=context,
    )


def test_one_action_fails_eligibility() -> None:
    action_id = uuid4()
    result = evaluate_eligibility(
        GoalLearning(
            goal_id=uuid4(),
            content="short loops work",
            status=LearningStatus.ACTIVE,
        ),
        [_action(context="milestone:1", action_id=action_id)],
    )
    assert result.eligible is False
    assert result.permitted_claim_kind is ClaimKind.INFERENCE


def test_same_lineage_retries_fail_diversity() -> None:
    action_id = uuid4()
    result = evaluate_eligibility(
        GoalLearning(
            goal_id=uuid4(),
            content="short loops work",
            status=LearningStatus.ACTIVE,
        ),
        [
            _action(context="milestone:1", action_id=action_id),
            _action(context="milestone:1", action_id=action_id),
        ],
    )
    assert result.eligible is False


def test_two_independent_contexts_pass_as_inference() -> None:
    result = evaluate_eligibility(
        GoalLearning(
            goal_id=uuid4(),
            content="short loops work",
            status=LearningStatus.ACTIVE,
        ),
        [_action(context="milestone:1"), _action(context="milestone:2")],
    )
    assert result.eligible is True
    assert result.permitted_claim_kind is ClaimKind.INFERENCE


def test_unresolved_contradiction_blocks() -> None:
    result = evaluate_eligibility(
        GoalLearning(
            goal_id=uuid4(),
            content="short loops work",
            status=LearningStatus.REVIEW_NEEDED,
        ),
        [
            _action(context="milestone:1"),
            LearningEvidenceDraft(
                evidence_kind=LearningEvidenceKind.ACTION_RECORD,
                role=LearningEvidenceRole.CONTRADICTS,
                excerpt="opposite outcome",
                action_record_id=uuid4(),
                execution_context_key="milestone:2",
            ),
        ],
    )
    assert result.eligible is False
    assert result.unresolved_contradiction is True


def test_generated_generalization_stays_inference() -> None:
    result = evaluate_eligibility(
        GoalLearning(
            goal_id=uuid4(),
            content="practice beats drills",
            claim_kind=ClaimKind.INFERENCE,
            status=LearningStatus.ACTIVE,
        ),
        [_action(context="milestone:1"), _action(context="milestone:2")],
        user_confirmed=False,
    )
    assert result.permitted_claim_kind is ClaimKind.INFERENCE


def test_user_confirmation_is_only_fact_route() -> None:
    result = evaluate_eligibility(
        GoalLearning(
            goal_id=uuid4(),
            content="I prefer morning study",
            claim_kind=ClaimKind.INFERENCE,
            status=LearningStatus.ACTIVE,
        ),
        [],
        user_confirmed=True,
    )
    assert result.eligible is True
    assert result.permitted_claim_kind is ClaimKind.FACT
