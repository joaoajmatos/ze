"""A datetime query value without a timezone offset is a 422 (phase 194, N-1)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.v0.actions.router import router as actions_router
from ze_api.api.v0.collisions.router import router as collisions_router
from ze_api.api.v0.loops.router import router as loops_router

API_KEY = "test-key"
NAIVE = "2026-10-01T00:00:00"
AWARE = "2026-10-01T00:00:00Z"


def _client() -> AsyncClient:
    app = FastAPI()
    store = AsyncMock()
    store.list_by_subject.return_value = []
    store.list.return_value = []
    app.state.container = SimpleNamespace(
        action_record_store=store, collision_store=store, loop_store=store
    )
    app.state.settings = SimpleNamespace(ze_api_key=API_KEY)
    for router in (actions_router, collisions_router, loops_router):
        app.include_router(router, prefix="/api/v0")
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {API_KEY}"},
    )


@pytest.mark.parametrize(
    "path",
    [
        f"/api/v0/actions?since={NAIVE}",
        f"/api/v0/collisions?since={NAIVE}",
        f"/api/v0/collisions?until={NAIVE}",
        f"/api/v0/loops?since={NAIVE}",
    ],
)
async def test_naive_datetime_is_422(path: str) -> None:
    async with _client() as client:
        response = await client.get(path)
    assert response.status_code == 422
    assert "timezone" in response.json()["detail"]


@pytest.mark.parametrize(
    "path",
    [
        f"/api/v0/actions?since={AWARE}",
        f"/api/v0/collisions?since={AWARE}&until={AWARE}",
        f"/api/v0/loops?since={AWARE}",
    ],
)
async def test_aware_datetime_is_accepted(path: str) -> None:
    async with _client() as client:
        response = await client.get(path)
    assert response.status_code == 200


async def test_unknown_loop_state_is_422() -> None:
    async with _client() as client:
        response = await client.get("/api/v0/loops?state=bogus")
    assert response.status_code == 422
