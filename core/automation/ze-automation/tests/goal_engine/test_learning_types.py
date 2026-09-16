from __future__ import annotations

from uuid import uuid4

import pytest
from ze_agents.claims import ClaimKind, Provenance
from ze_agents.errors import GoalLearningError, GoalLearningEvidenceError

from ze_automation.goals.learning import evaluate_eligibility, validate_learning_draft
from ze_automation.goals.types import (
    GoalLearning,
    LearningEvidenceDraft,
    LearningEvidenceKind,
    LearningEvidenceRole,
    LearningStatus,
)


def _draft(**overrides) -> LearningEvidenceDraft:
    base = dict(
        evidence_kind=LearningEvidenceKind.ACTION_RECORD,
        role=LearningEvidenceRole.SUPPORTS,
        excerpt="trace succeeded",
        action_record_id=uuid4(),
        execution_context_key="milestone:a",
    )
    base.update(overrides)
    return LearningEvidenceDraft(**base)


def test_empty_content_rejected() -> None:
    with pytest.raises(GoalLearningError):
        validate_learning_draft(
            GoalLearning(goal_id=uuid4(), content="  "),
            [_draft()],
        )


def test_confidence_bounds() -> None:
    with pytest.raises(GoalLearningError):
        validate_learning_draft(
            GoalLearning(goal_id=uuid4(), content="ok", confidence=1.2),
            [_draft()],
        )


def test_action_record_claim_kind_rejected() -> None:
    with pytest.raises(GoalLearningError):
        validate_learning_draft(
            GoalLearning(
                goal_id=uuid4(),
                content="did a thing",
                claim_kind=ClaimKind.ACTION_RECORD,
            ),
            [_draft()],
        )


def test_missing_evidence_rejected_for_automated_learning() -> None:
    with pytest.raises(GoalLearningEvidenceError):
        validate_learning_draft(
            GoalLearning(
                goal_id=uuid4(),
                content="pattern",
                provenance=Provenance.SYNTHESIZED,
            ),
            [],
        )


def test_dual_source_evidence_rejected() -> None:
    with pytest.raises(GoalLearningEvidenceError):
        validate_learning_draft(
            GoalLearning(goal_id=uuid4(), content="pattern"),
            [
                _draft(review_id=uuid4()),
            ],
        )


def test_one_action_fails_diversity_gate() -> None:
    action_id = uuid4()
    learning = GoalLearning(
        goal_id=uuid4(),
        content="short loops work",
        status=LearningStatus.ACTIVE,
    )
    evidence = [
        _draft(action_record_id=action_id, execution_context_key="milestone:1"),
        _draft(action_record_id=action_id, execution_context_key="milestone:1"),
    ]
    result = evaluate_eligibility(learning, evidence)
    assert result.eligible is False
    assert result.permitted_claim_kind is ClaimKind.INFERENCE


def test_two_independent_contexts_are_eligible_as_inference() -> None:
    learning = GoalLearning(
        goal_id=uuid4(),
        content="short loops work",
        status=LearningStatus.ACTIVE,
    )
    evidence = [
        _draft(execution_context_key="milestone:1"),
        _draft(execution_context_key="milestone:2"),
    ]
    result = evaluate_eligibility(learning, evidence)
    assert result.eligible is True
    assert result.independent_context_count == 2
    assert result.permitted_claim_kind is ClaimKind.INFERENCE


def test_user_confirmation_permits_fact() -> None:
    learning = GoalLearning(
        goal_id=uuid4(),
        content="I prefer morning study",
        status=LearningStatus.ACTIVE,
    )
    result = evaluate_eligibility(learning, [], user_confirmed=True)
    assert result.eligible is True
    assert result.permitted_claim_kind is ClaimKind.FACT
