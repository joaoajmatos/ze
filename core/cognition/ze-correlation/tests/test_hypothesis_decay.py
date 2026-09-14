"""Unit tests for HypothesisDecayJob (Phase 111, User Story 1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ze_agents.claims import ClaimKind
from ze_correlation.jobs.hypothesis_decay import HypothesisDecayJob
from ze_correlation.push import passes_confidence
from ze_correlation.types import Hypothesis

UTC = timezone.utc


def _make_hypothesis(confidence: float, created_at: datetime) -> Hypothesis:
    return Hypothesis(
        id=uuid4(),
        summary="test",
        narrative="test",
        relation="pattern",
        confidence=confidence,
        relevance=0.5,
        evidence=[],
        entities=[],
        created_at=created_at,
        claim_kind=ClaimKind.INFERENCE,
    )


@pytest.mark.asyncio
async def test_decayed_hypothesis_gets_lower_confidence_and_logs():
    old = _make_hypothesis(0.8, datetime.now(UTC) - timedelta(days=31))
    store = AsyncMock()
    store.list_decay_candidates.return_value = [old]

    job = HypothesisDecayJob(hypothesis_store=store)
    await job.run()

    store.set_confidence.assert_awaited_once()
    call_args = store.set_confidence.await_args
    assert call_args.args[0] == old.id
    new_confidence = call_args.args[1]
    assert new_confidence < 0.8
    assert new_confidence == pytest.approx(0.77)


@pytest.mark.asyncio
async def test_hypothesis_within_window_is_untouched():
    store = AsyncMock()
    store.list_decay_candidates.return_value = []

    job = HypothesisDecayJob(hypothesis_store=store)
    await job.run()

    store.set_confidence.assert_not_awaited()


@pytest.mark.asyncio
async def test_decayed_confidence_fails_push_bar_once_crossed():
    old = _make_hypothesis(0.62, datetime.now(UTC) - timedelta(days=31))
    store = AsyncMock()
    store.list_decay_candidates.return_value = [old]

    job = HypothesisDecayJob(hypothesis_store=store)
    await job.run()

    new_confidence = store.set_confidence.await_args.args[1]
    assert passes_confidence(old.confidence, tau=0.6)
    assert not passes_confidence(new_confidence, tau=0.6)
