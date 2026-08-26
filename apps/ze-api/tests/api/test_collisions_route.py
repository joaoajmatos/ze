"""Integration-style tests for /api/v0/collisions (Phase 126)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from ze_agents.claims import ClaimKind
from ze_plugin.contribution import SourceFunction, TargetFace

from ze_api.api.routes.collisions import router
from ze_collision.types import CollisionLogEntry

API_KEY = "test-key"


def _entry(**overrides) -> CollisionLogEntry:
    defaults = dict(
        id=uuid4(),
        contribution_a_domain_id=uuid4(),
        contribution_a_producer_kind="open_loop",
        contribution_a_source_function=SourceFunction.PERCEPTION,
        contribution_a_claim_kind=ClaimKind.FACT,
        contribution_b_domain_id=uuid4(),
        contribution_b_producer_kind="hypothesis",
        contribution_b_source_function=SourceFunction.REFLECTION,
        contribution_b_claim_kind=ClaimKind.INFERENCE,
        matched_entity_id=uuid4(),
        matched_target_face=TargetFace.WORLD,
        conflict_summary="X moved to Berlin vs X is still in Lisbon",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return CollisionLogEntry(**defaults)


def _make_app(collision_store=None) -> tuple[FastAPI, AsyncMock]:
    app = FastAPI()
    store = collision_store or AsyncMock()
    container = SimpleNamespace(collision_store=store)
    app.state.container = container
    app.state.settings = SimpleNamespace(ze_api_key=API_KEY)
    app.include_router(router, prefix="/api/v0")
    return app, store


@pytest.mark.asyncio
async def test_list_collisions_requires_auth():
    app, _ = _make_app()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v0/collisions")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_collisions_returns_matching_shape():
    entry = _entry()
    store = AsyncMock()
    store.list = AsyncMock(return_value=[entry])
    app, store = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/collisions", headers={"Authorization": f"Bearer {API_KEY}"}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["id"] == str(entry.id)
    assert item["contribution_a"]["domain_id"] == str(entry.contribution_a_domain_id)
    assert item["contribution_a"]["producer_kind"] == "open_loop"
    assert item["contribution_a"]["source_function"] == "perception"
    assert item["contribution_b"]["source_function"] == "reflection"
    assert item["matched_entity_id"] == str(entry.matched_entity_id)
    assert item["matched_target_face"] == "world"
    assert item["conflict_summary"] == entry.conflict_summary


@pytest.mark.asyncio
async def test_list_collisions_applies_query_params():
    store = AsyncMock()
    store.list = AsyncMock(return_value=[])
    app, store = _make_app(store)
    entity_id = uuid4()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/collisions",
            params={
                "entity_id": str(entity_id),
                "source_function": "reflection",
                "since": "2026-01-01T00:00:00Z",
                "until": "2026-02-01T00:00:00Z",
                "limit": 10,
            },
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json() == []
    _, kwargs = store.list.await_args
    assert kwargs["entity_id"] == entity_id
    assert kwargs["source_function"] == SourceFunction.REFLECTION
    assert kwargs["limit"] == 10
