"""Tests for GET /api/v0/proactive/job-runs (phase 185)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.deps import get_job_run_store, require_api_key
from ze_api.api.v0.proactive.router import router
from ze_proactive.types import JobRun

NOW = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)


def _run(job_id, hours_ago, status="ok", finished=True):
    started = NOW - timedelta(hours=hours_ago)
    return JobRun(
        job_id=job_id,
        last_started_at=started,
        last_finished_at=started + timedelta(minutes=1) if finished else None,
        last_status=status,
    )


def _client(store, *, auth_override=True) -> AsyncClient:
    app = FastAPI()
    app.state.settings = SimpleNamespace(ze_api_key="secret")
    if auth_override:
        app.dependency_overrides[require_api_key] = lambda: None
    app.dependency_overrides[get_job_run_store] = lambda: store
    app.include_router(router, prefix="/api/v0")
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_lists_last_run_per_job_newest_first():
    store = SimpleNamespace(
        list_runs=AsyncMock(
            return_value=[_run("a", 10), _run("b", 2), _run("c", 5, "running", False)]
        )
    )
    async with _client(store) as c:
        resp = await c.get("/api/v0/proactive/job-runs")
    assert resp.status_code == 200
    body = resp.json()
    assert [r["job_id"] for r in body] == ["b", "c", "a"]
    assert body[1]["last_status"] == "running"
    assert body[1]["last_finished_at"] is None
    assert set(body[0]) == {
        "job_id",
        "last_started_at",
        "last_finished_at",
        "last_status",
    }


@pytest.mark.asyncio
async def test_since_filters_on_last_started_at():
    store = SimpleNamespace(
        list_runs=AsyncMock(return_value=[_run("a", 10), _run("b", 2)])
    )
    since = (NOW - timedelta(hours=3)).isoformat()
    async with _client(store) as c:
        resp = await c.get("/api/v0/proactive/job-runs", params={"since": since})
    assert [r["job_id"] for r in resp.json()] == ["b"]


@pytest.mark.asyncio
async def test_store_failure_is_503_not_an_empty_list():
    store = SimpleNamespace(list_runs=AsyncMock(side_effect=RuntimeError("db")))
    async with _client(store) as c:
        resp = await c.get("/api/v0/proactive/job-runs")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_requires_api_key():
    store = SimpleNamespace(list_runs=AsyncMock(return_value=[]))
    async with _client(store, auth_override=False) as c:
        resp = await c.get("/api/v0/proactive/job-runs")
    assert resp.status_code in (401, 403)
