"""Tests for GET /api/v0/activity/heatmap."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.deps import require_api_key
from ze_api.api.routes.activity import router


def _make_app(rows) -> tuple[FastAPI, AsyncMock]:
    store = AsyncMock()
    store.agent_activity_by_day = AsyncMock(return_value=rows)
    app = FastAPI()
    app.state.container = SimpleNamespace(message_store=store)
    app.dependency_overrides[require_api_key] = lambda: None
    app.include_router(router, prefix="/api/v0")
    return app, store


async def test_heatmap_groups_store_rows_by_day():
    app, store = _make_app(
        [
            (date(2026, 10, 1), "research", 3),
            (date(2026, 10, 1), "companion", 1),
            (date(2026, 10, 2), "research", 2),
        ]
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/activity/heatmap",
            params={"start": "2026-10-01", "end": "2026-10-02"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["agents"] == ["companion", "research"]
    assert [d["date"] for d in body["days"]] == ["2026-10-01", "2026-10-02"]
    assert [d["total"] for d in body["days"]] == [4, 2]
    assert body["start"] == "2026-10-01"
    start_dt, end_dt = store.agent_activity_by_day.call_args[0]
    assert start_dt == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert end_dt == datetime(2026, 10, 3, tzinfo=timezone.utc)
