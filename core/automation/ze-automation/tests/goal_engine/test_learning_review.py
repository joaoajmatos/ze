from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_automation.goals.postgres import PostgresGoalStore
from ze_automation.goals.types import LearningReviewDecision, LearningStatus


def _pool():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock()
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


def _claim_row(**overrides):
    row = {
        "id": uuid4(),
        "goal_id": uuid4(),
        "content": "candidate",
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
    row.update(overrides)
    return row


async def test_approve_records_user_confirmation_and_activates():
    pool, conn = _pool()
    learning_id = uuid4()
    pending = _claim_row(id=learning_id)
    active = _claim_row(id=learning_id, status="active")
    review = {"id": uuid4()}
    conn.fetchrow = AsyncMock(side_effect=[pending, review, active])
    conn.fetch = AsyncMock(side_effect=[[], []])
    store = PostgresGoalStore(pool)
    result = await store.review_learning(learning_id, LearningReviewDecision.APPROVE)
    assert result.status is LearningStatus.ACTIVE
    executed = " ".join(call.args[0] for call in conn.execute.call_args_list)
    assert "user_confirmation" in executed
    assert "active" in executed


async def test_reject_retracts():
    pool, conn = _pool()
    learning_id = uuid4()
    pending = _claim_row(id=learning_id)
    retracted = _claim_row(
        id=learning_id, status="retracted", retracted_at="now"
    )
    conn.fetchrow = AsyncMock(side_effect=[pending, {"id": uuid4()}, retracted])
    conn.fetch = AsyncMock(side_effect=[[], []])
    store = PostgresGoalStore(pool)
    result = await store.review_learning(learning_id, LearningReviewDecision.REJECT)
    assert result.status is LearningStatus.RETRACTED


async def test_correct_supersedes_and_creates_new_claim():
    pool, conn = _pool()
    original_id = uuid4()
    new_id = uuid4()
    original = _claim_row(id=original_id)
    new_row = _claim_row(id=new_id, status="active", provenance="prompt_supplied")
    conn.fetchrow = AsyncMock(
        side_effect=[original, {"id": uuid4()}, new_row, new_row]
    )
    conn.fetch = AsyncMock(side_effect=[[], []])
    store = PostgresGoalStore(pool)
    result = await store.review_learning(
        original_id,
        LearningReviewDecision.CORRECT,
        corrected_content="corrected assertion",
    )
    assert result.id == new_id
    executed = " ".join(call.args[0] for call in conn.execute.call_args_list)
    assert "superseded" in executed
    assert "supersedes" in executed
