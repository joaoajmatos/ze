from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ze_api.api import deps
from ze_api.api.v0.costs import router as costs
from ze_api.api.v0.goals import router as goals


@pytest.fixture
def container():
    gate_id = uuid4()
    goal = SimpleNamespace(
        id=uuid4(),
        title="Launch product",
        objective="Launch product",
        status=SimpleNamespace(value="active"),
        created_at="2026-06-01T00:00:00+00:00",
    )

    progress = SimpleNamespace(
        goal=goal,
        milestones_done=2,
        milestones_total=5,
        next_milestone="Draft the landing page",
        gate_id=gate_id,
        gate_title="Approve pricing",
        gate_open_since=datetime(2026, 6, 2, tzinfo=timezone.utc),
        last_progress_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        stuck_since=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    goal_store = AsyncMock()
    goal_store.list_progress = AsyncMock(return_value=[progress])

    return SimpleNamespace(
        _plugin_stores={
            "goal_store": goal_store,
        },
    )


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.fixture
def client(container, mock_pool):
    pool, conn = mock_pool
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(
        return_value={"total_tokens": 0, "total_cost_usd": 0, "total_calls": 0}
    )

    container.pool = pool

    app = FastAPI()
    app.state.container = container
    app.include_router(goals.router, prefix="/api/v0")
    app.include_router(costs.router, prefix="/api/v0")

    app.dependency_overrides[deps.require_api_key] = lambda: None

    with TestClient(app) as c:
        yield c


def test_list_goals(client):
    resp = client.get("/api/v0/goals")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Launch product"
    assert data[0]["objective"] == "Launch product"
    assert data[0]["status"] == "active"


def test_list_goals_carries_progress_fields(client, container):
    [row] = client.get("/api/v0/goals").json()
    assert row["milestones_done"] == 2
    assert row["milestones_total"] == 5
    assert row["next_milestone"] == "Draft the landing page"
    assert row["gate_id"] is not None
    assert row["gate_title"] == "Approve pricing"
    assert row["gate_open_since"].startswith("2026-06-02")
    assert row["last_progress_at"].startswith("2026-06-01")
    assert row["stuck_since"].startswith("2026-06-01")


def test_start_goal(client, container):
    goal_id = uuid4()
    executor = AsyncMock()
    executor.approve_plan = AsyncMock(return_value=True)
    store = AsyncMock()
    store.get_goal = AsyncMock(
        return_value=SimpleNamespace(id=goal_id, status=SimpleNamespace(value="active"))
    )
    container._plugin_stores["goal_executor"] = executor
    container._plugin_stores["goal_store"] = store
    container.connection_manager = AsyncMock()
    container.connection_manager.send_frame = AsyncMock()

    resp = client.post(f"/api/v0/goals/{goal_id}/start")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"
    executor.approve_plan.assert_awaited_once_with(goal_id)


def test_web_cost_summary(client):
    resp = client.get("/api/v0/costs/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_usd"] == 0
    assert data["total_tokens"] == 0
    assert data["total_calls"] == 0
    assert data["period"] == "Last 30 days"
    assert data["by_agent"] == {}
