from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_agents.claims import ClaimKind, Provenance
from ze_automation.goals.postgres import PostgresGoalStore
from ze_automation.goals.types import (
    GoalLearning,
    LearningEvidenceDraft,
    LearningEvidenceKind,
    LearningEvidenceRole,
    LearningStatus,
)


def _pool(fetchrow=None):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()

    @asynccontextmanager
    async def transaction():
        yield

    conn.transaction = transaction

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    return pool, conn


async def test_create_learning_inserts_claim_and_evidence():
    learning_id = uuid4()
    evidence_id = uuid4()
    action_id = uuid4()
    claim_row = {
        "id": learning_id,
        "goal_id": uuid4(),
        "content": "short loops work",
        "claim_kind": "inference",
        "provenance": "synthesized",
        "confidence": 0.4,
        "status": "pending_review",
        "created_at": None,
        "updated_at": None,
        "activated_at": None,
        "retracted_at": None,
        "superseded_by_id": None,
    }
    evidence_row = {
        "id": evidence_id,
        "learning_id": learning_id,
        "evidence_kind": "action_record",
        "role": "supports",
        "excerpt": "trace succeeded",
        "action_record_id": action_id,
        "review_id": None,
        "execution_context_key": "milestone:1",
        "created_at": None,
    }
    conn_fetch = AsyncMock(side_effect=[claim_row, evidence_row])
    pool, conn = _pool()
    conn.fetchrow = conn_fetch
    store = PostgresGoalStore(pool)
    created = await store.create_learning(
        GoalLearning(
            goal_id=claim_row["goal_id"],
            content="short loops work",
            claim_kind=ClaimKind.INFERENCE,
            provenance=Provenance.SYNTHESIZED,
            status=LearningStatus.PENDING_REVIEW,
        ),
        [
            LearningEvidenceDraft(
                evidence_kind=LearningEvidenceKind.ACTION_RECORD,
                role=LearningEvidenceRole.SUPPORTS,
                excerpt="trace succeeded",
                action_record_id=action_id,
                execution_context_key="milestone:1",
            )
        ],
    )
    assert created.id == learning_id
    assert created.claim_kind is ClaimKind.INFERENCE
    assert len(created.evidence) == 1
    assert created.evidence[0].action_record_id == action_id
    assert "goal_learning_claims" in conn_fetch.await_args_list[0].args[0]
    assert "goal_learning_evidence" in conn_fetch.await_args_list[1].args[0]
