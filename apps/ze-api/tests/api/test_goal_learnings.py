from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ze_api.api import dependencies
from ze_api.api.routes import goals


def _summary(**overrides):
    from datetime import datetime, timezone

    from ze_agents.claims import ClaimKind, Provenance
    from ze_automation.goals.types import LearningPromotionState, LearningStatus

    data = dict(
        id=uuid4(),
        content="short loops work",
        claim_kind=ClaimKind.INFERENCE,
        provenance=Provenance.SYNTHESIZED,
        confidence=0.4,
        status=LearningStatus.PENDING_REVIEW,
        evidence_count=1,
        promotion_state=None,
        review_needed=True,
        created_at=datetime.now(timezone.utc),
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def _client(store):
    app = FastAPI()
    app.state.container = SimpleNamespace(_plugin_stores={"goal_store": store})
    app.include_router(goals.router, prefix="/api/v0")
    app.dependency_overrides[dependencies.require_api_key] = lambda: None
    return TestClient(app)


def test_list_learnings_returns_summaries():
    store = AsyncMock()
    row = _summary()
    store.list_goal_learnings = AsyncMock(return_value=[row])
    client = _client(store)
    resp = client.get(f"/api/v0/goals/{uuid4()}/learnings")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["claim_kind"] == "inference"
    assert "raw" not in body[0]


def test_review_validation_rejects_unknown_decision():
    store = AsyncMock()
    client = _client(store)
    resp = client.post(
        f"/api/v0/goals/{uuid4()}/learnings/{uuid4()}/review",
        json={"decision": "arbitrate"},
    )
    assert resp.status_code == 422


def test_promote_returns_blocked_state():
    from ze_automation.goals.types import LearningPromotion, LearningPromotionState

    goal_id = uuid4()
    learning_id = uuid4()
    store = AsyncMock()
    store.get_learning = AsyncMock(
        return_value=SimpleNamespace(id=learning_id, goal_id=goal_id)
    )
    store.promote_learning = AsyncMock(
        return_value=LearningPromotion(
            id=uuid4(),
            learning_id=learning_id,
            state=LearningPromotionState.BLOCKED,
            failure_reason="insufficient independent evidence",
        )
    )
    client = _client(store)
    resp = client.post(f"/api/v0/goals/{goal_id}/learnings/{learning_id}/promote")
    assert resp.status_code == 200
    assert resp.json()["state"] == "blocked"


def test_learning_detail_exposes_evidence_excerpt_not_payload():
    from ze_agents.claims import ClaimKind, Provenance
    from ze_automation.goals.types import (
        GoalLearning,
        LearningEvidence,
        LearningEvidenceKind,
        LearningEvidenceRole,
        LearningStatus,
    )

    goal_id = uuid4()
    learning_id = uuid4()
    store = AsyncMock()
    store.get_learning = AsyncMock(
        return_value=GoalLearning(
            id=learning_id,
            goal_id=goal_id,
            content="short loops work",
            claim_kind=ClaimKind.INFERENCE,
            provenance=Provenance.SYNTHESIZED,
            status=LearningStatus.ACTIVE,
            evidence=[
                LearningEvidence(
                    id=uuid4(),
                    learning_id=learning_id,
                    evidence_kind=LearningEvidenceKind.ACTION_RECORD,
                    role=LearningEvidenceRole.SUPPORTS,
                    excerpt="trace succeeded",
                    action_record_id=uuid4(),
                    execution_context_key="milestone:1",
                )
            ],
        )
    )
    store.list_goal_learnings = AsyncMock(return_value=[_summary(id=learning_id)])
    client = _client(store)
    resp = client.get(f"/api/v0/goals/{goal_id}/learnings/{learning_id}")
    assert resp.status_code == 200
    evidence = resp.json()["evidence"][0]
    assert evidence["excerpt"] == "trace succeeded"
    assert "payload" not in evidence
