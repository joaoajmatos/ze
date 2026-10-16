from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ze_api.api import deps
from ze_api.api.routes import goals


def _summary(**overrides):
    from datetime import datetime, timezone

    from ze_agents.claims import ClaimKind, Provenance
    from ze_automation.goals.types import LearningStatus

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
    app.dependency_overrides[deps.require_api_key] = lambda: None
    return TestClient(app)


def test_review_validation_rejects_unknown_decision():
    store = AsyncMock()
    client = _client(store)
    resp = client.post(
        f"/api/v0/goals/{uuid4()}/learnings/{uuid4()}/review",
        json={"decision": "arbitrate"},
    )
    assert resp.status_code == 422
