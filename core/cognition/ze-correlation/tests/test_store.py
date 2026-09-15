"""Tests for PostgresHypothesisStore (Phase 130 additions: confirm, mark_promoted,
list_by_entities, update_evidence)."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze_correlation.store import HypothesisNotFoundError, PostgresHypothesisStore

UTC = timezone.utc


def _make_pool(fetchrow_return=None, fetch_return=None):
    """Return a mock asyncpg pool whose fetchrow/fetch return canned data."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    conn.fetch = AsyncMock(return_value=fetch_return or [])
    conn.execute = AsyncMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = _acquire
    return pool, conn


def _row(hypothesis_id, *, entities=None, confirmed=False, promoted_at=None):
    return {
        "id": hypothesis_id,
        "summary": "Alice may work on Launch",
        "narrative": "reply-and-meeting co-occurrence",
        "relation": "pattern",
        "confidence": 0.6,
        "relevance": 0.5,
        "evidence": json.dumps([]),
        "entities": json.dumps([str(e) for e in (entities or [])]),
        "created_at": datetime.now(UTC),
        "surfaced": False,
        "feedback": None,
        "claim_kind": "inference",
        "confirmed": confirmed,
        "promoted_at": promoted_at,
    }


class TestConfirm:
    async def test_flips_confirmed_flag(self):
        hyp_id = uuid4()
        pool, conn = _make_pool(fetchrow_return=_row(hyp_id, confirmed=True))
        store = PostgresHypothesisStore(pool=pool)

        result = await store.confirm(hyp_id)

        assert result.confirmed is True
        conn.fetchrow.assert_awaited_once()

    async def test_raises_when_not_found(self):
        pool, _ = _make_pool(fetchrow_return=None)
        store = PostgresHypothesisStore(pool=pool)

        with pytest.raises(HypothesisNotFoundError):
            await store.confirm(uuid4())


class TestMarkPromoted:
    async def test_sets_promoted_at(self):
        hyp_id = uuid4()
        promoted_at = datetime.now(UTC)
        pool, conn = _make_pool(
            fetchrow_return=_row(hyp_id, promoted_at=promoted_at)
        )
        store = PostgresHypothesisStore(pool=pool)

        result = await store.mark_promoted(hyp_id)

        assert result.promoted_at == promoted_at
        conn.fetchrow.assert_awaited_once()

    async def test_raises_when_not_found(self):
        pool, _ = _make_pool(fetchrow_return=None)
        store = PostgresHypothesisStore(pool=pool)

        with pytest.raises(HypothesisNotFoundError):
            await store.mark_promoted(uuid4())


class TestListByEntities:
    async def test_returns_hydrated_hypotheses(self):
        hyp_id = uuid4()
        person_id, project_id = uuid4(), uuid4()
        pool, conn = _make_pool(
            fetch_return=[_row(hyp_id, entities=[person_id, project_id])]
        )
        store = PostgresHypothesisStore(pool=pool)

        results = await store.list_by_entities([project_id])

        assert len(results) == 1
        assert results[0].id == hyp_id
        assert project_id in results[0].entities

    async def test_empty_entity_list_short_circuits(self):
        pool, conn = _make_pool()
        store = PostgresHypothesisStore(pool=pool)

        results = await store.list_by_entities([])

        assert results == []
        conn.fetch.assert_not_awaited()


class TestUpdateEvidence:
    async def test_updates_evidence_and_confidence(self):
        hyp_id = uuid4()
        pool, conn = _make_pool()
        store = PostgresHypothesisStore(pool=pool)

        await store.update_evidence(hyp_id, evidence=[], confidence=0.75)

        conn.execute.assert_awaited_once()
        args = conn.execute.await_args.args
        assert "UPDATE correlation_hypothesis" in args[0]
        assert args[2] == 0.75
        assert args[3] == hyp_id
