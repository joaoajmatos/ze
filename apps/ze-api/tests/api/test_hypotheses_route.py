"""Tests for /api/v0/hypotheses (phase 185)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_agents.claims import ClaimKind
from ze_api.api.deps import get_entity_names, get_hypothesis_store, require_api_key
from ze_api.api.v0.hypotheses.router import router
from ze_correlation.store import HypothesisNotFoundError
from ze_correlation.types import Hypothesis

NOW = datetime(2026, 10, 17, 9, tzinfo=timezone.utc)


def _hyp(entities, **kw) -> Hypothesis:
    return Hypothesis(
        id=uuid4(),
        summary="Alice may work on Launch",
        narrative="n",
        relation="pattern",
        confidence=0.6,
        relevance=0.5,
        evidence=[],
        entities=entities,
        created_at=NOW,
        claim_kind=kw.pop("claim_kind", ClaimKind.INFERENCE),
        **kw,
    )


class FakeStore:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []
        self.feedback_calls = []

    async def list_for_display(self, *, entity_id, state, limit):
        self.calls.append((entity_id, state, limit))
        rows = self.rows
        if entity_id is not None:
            rows = [h for h in rows if entity_id in h.entities]
        return rows[:limit]

    async def set_feedback(self, hypothesis_id, feedback):
        self.feedback_calls.append((hypothesis_id, feedback))
        for h in self.rows:
            if h.id == hypothesis_id:
                h.feedback = feedback
                return h
        raise HypothesisNotFoundError(str(hypothesis_id))


def _client(store, names=None, *, auth=True) -> AsyncClient:
    async def entity_names(ids):
        return names or {}

    app = FastAPI()
    app.state.settings = SimpleNamespace(ze_api_key="secret")
    if auth:
        app.dependency_overrides[require_api_key] = lambda: None
    app.dependency_overrides[get_hypothesis_store] = lambda: store
    app.dependency_overrides[get_entity_names] = lambda: entity_names
    app.include_router(router, prefix="/api/v0")
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_entity_filter_returns_two_of_three():
    e1, e2 = uuid4(), uuid4()
    store = FakeStore([_hyp([e1]), _hyp([e1, e2]), _hyp([e2])])
    async with _client(store, {e1: "Alice"}) as c:
        resp = await c.get("/api/v0/hypotheses", params={"entity_id": str(e1)})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["entities"][0] == {"id": str(e1), "name": "Alice"}
    assert {h["claim_kind"] for h in body} <= {"inference", "suspicion"}


@pytest.mark.asyncio
async def test_state_defaults_to_open_and_is_a_closed_enum():
    store = FakeStore([])
    async with _client(store) as c:
        assert (await c.get("/api/v0/hypotheses")).status_code == 200
        bad = await c.get("/api/v0/hypotheses", params={"state": "weird"})
    assert store.calls[0][1] == "open"
    assert bad.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("limit,expected", [(0, 1), (500, 200), (7, 7)])
async def test_limit_is_clamped(limit, expected):
    store = FakeStore([])
    async with _client(store) as c:
        await c.get("/api/v0/hypotheses", params={"limit": limit})
    assert store.calls[0][2] == expected


@pytest.mark.asyncio
async def test_feedback_sets_and_clears():
    h = _hyp([uuid4()])
    store = FakeStore([h])
    async with _client(store) as c:
        resp = await c.post(
            f"/api/v0/hypotheses/{h.id}/feedback", json={"feedback": "muted"}
        )
        assert resp.status_code == 200 and resp.json()["feedback"] == "muted"
        cleared = await c.post(
            f"/api/v0/hypotheses/{h.id}/feedback", json={"feedback": None}
        )
    assert cleared.status_code == 200 and cleared.json()["feedback"] is None
    assert store.feedback_calls == [(h.id, "muted"), (h.id, None)]


@pytest.mark.asyncio
async def test_feedback_unknown_id_404_and_bad_value_422():
    store = FakeStore([])
    async with _client(store) as c:
        missing = await c.post(
            f"/api/v0/hypotheses/{uuid4()}/feedback", json={"feedback": "useful"}
        )
        bad = await c.post(
            f"/api/v0/hypotheses/{uuid4()}/feedback", json={"feedback": "loved"}
        )
    assert missing.status_code == 404
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_requires_api_key():
    async with _client(FakeStore([]), auth=False) as c:
        resp = await c.get("/api/v0/hypotheses")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_entity_name_adapter_maps_memory_entities():
    from unittest.mock import AsyncMock

    from ze_api.api.deps import get_entity_names

    eid = uuid4()
    memory_store = SimpleNamespace(
        get_entities_by_ids=AsyncMock(
            return_value=[SimpleNamespace(id=eid, canonical_name="Alice")]
        )
    )
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(container=SimpleNamespace(memory_store=memory_store)))
    )
    lookup = get_entity_names(request)
    assert await lookup([eid]) == {eid: "Alice"}
