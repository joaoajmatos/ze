"""Contract tests for POST /api/v0/workspace/runs/{id}/cancel (Phase 116, User
Story 3). Exercises the FastAPI route layer against fake WorkspaceStore/
WorkspaceClient/RunWatcher — SQL and RunWatcher.cancel() unit behavior are
covered by core/ze-workspace/tests/{test_store,test_followthrough}.py.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ze_api.api import dependencies
from ze_api.api.routes import workspace as workspace_route
from ze_workspace.followthrough import RunWatcher
from ze_workspace.types import WorkspaceRun, WorkspaceRunOrigin, WorkspaceRunStatus


def _in_progress_run(run_id) -> WorkspaceRun:
    return WorkspaceRun(
        id=run_id,
        command="sleep 60",
        origin=WorkspaceRunOrigin.CONVERSATION,
        status=None,
        started_at=datetime.now(timezone.utc),
        ended_at=None,
        thread_id="t1",
    )


class FakeStore:
    def __init__(self, run: WorkspaceRun | None) -> None:
        self._run = run

    async def get_run(self, run_id):
        if self._run is not None and self._run.id == run_id:
            return self._run
        return None


@pytest.fixture
def app_and_client():
    def _build(run: WorkspaceRun | None, run_watcher):
        app = FastAPI()
        app.state.container = SimpleNamespace(
            workspace_store=FakeStore(run),
            workspace_client=AsyncMock(),
            workspace_run_watcher=run_watcher,
        )
        app.include_router(workspace_route.router, prefix="/api/v0")
        app.dependency_overrides[dependencies.require_api_key] = lambda: None
        return TestClient(app)

    return _build


def test_cancel_success_within_15s(app_and_client):
    run_id = uuid4()
    run = _in_progress_run(run_id)
    cancelled = WorkspaceRun(
        id=run_id,
        command=run.command,
        origin=run.origin,
        status=WorkspaceRunStatus.CANCELLED,
        started_at=run.started_at,
        ended_at=datetime.now(timezone.utc),
        thread_id=run.thread_id,
    )
    run_watcher = SimpleNamespace(cancel=AsyncMock(return_value=cancelled))
    client = app_and_client(run, run_watcher)

    start = time.monotonic()
    resp = client.post(f"/api/v0/workspace/runs/{run_id}/cancel")
    elapsed = time.monotonic() - start

    assert elapsed < 15
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["ended_at"] is not None
    run_watcher.cancel.assert_awaited_once_with(run_id)


def test_cancel_already_finished_returns_409(app_and_client):
    run_id = uuid4()
    run = _in_progress_run(run_id)
    run.ended_at = datetime.now(timezone.utc)
    run.status = WorkspaceRunStatus.SUCCEEDED
    run_watcher = SimpleNamespace(cancel=AsyncMock())
    client = app_and_client(run, run_watcher)

    resp = client.post(f"/api/v0/workspace/runs/{run_id}/cancel")

    assert resp.status_code == 409
    run_watcher.cancel.assert_not_awaited()


def test_cancel_unknown_run_returns_404(app_and_client):
    run_watcher = SimpleNamespace(cancel=AsyncMock())
    client = app_and_client(None, run_watcher)

    resp = client.post(f"/api/v0/workspace/runs/{uuid4()}/cancel")

    assert resp.status_code == 404
    run_watcher.cancel.assert_not_awaited()


def test_second_cancel_on_same_run_returns_409(app_and_client):
    """RunWatcher.cancel() returning None (already terminal) is the race case —
    e.g. two concurrent cancel calls, or a natural finish landing first."""
    run_id = uuid4()
    run = _in_progress_run(run_id)
    run_watcher = SimpleNamespace(cancel=AsyncMock(return_value=None))
    client = app_and_client(run, run_watcher)

    resp = client.post(f"/api/v0/workspace/runs/{run_id}/cancel")

    assert resp.status_code == 409


def test_cancel_route_is_real_run_watcher_end_to_end():
    """Not a fake RunWatcher — exercises the real ze_workspace.followthrough
    class through the route, proving the wiring (store.get_run -> client.cancel
    -> run_watcher.cancel -> store.cancel_run + dispatch) actually fits together."""

    class RealBackedStore:
        def __init__(self, run: WorkspaceRun) -> None:
            self.runs = {run.id: run}

        async def get_run(self, run_id):
            return self.runs.get(run_id)

        async def cancel_run(self, run_id):
            run = self.runs.get(run_id)
            if run is None or run.ended_at is not None:
                return None
            cancelled = WorkspaceRun(
                id=run.id,
                command=run.command,
                origin=run.origin,
                status=WorkspaceRunStatus.CANCELLED,
                started_at=run.started_at,
                ended_at=datetime.now(timezone.utc),
                thread_id=run.thread_id,
            )
            self.runs[run_id] = cancelled
            return cancelled

        async def mark_follow_through_notified(self, run_id):
            return True

    run_id = uuid4()
    run = _in_progress_run(run_id)
    store = RealBackedStore(run)
    turn_starter = SimpleNamespace(invoke_raw_turn=AsyncMock())
    push_sender = SimpleNamespace(send_completion=AsyncMock())
    run_watcher = RunWatcher(store, turn_starter, push_sender)

    app = FastAPI()
    app.state.container = SimpleNamespace(
        workspace_store=store,
        workspace_client=AsyncMock(),
        workspace_run_watcher=run_watcher,
    )
    app.include_router(workspace_route.router, prefix="/api/v0")
    app.dependency_overrides[dependencies.require_api_key] = lambda: None

    with TestClient(app) as client:
        resp = client.post(f"/api/v0/workspace/runs/{run_id}/cancel")

    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
    turn_starter.invoke_raw_turn.assert_awaited_once()
    assert "stopped" in turn_starter.invoke_raw_turn.await_args.args[1]
    push_sender.send_completion.assert_awaited_once()
