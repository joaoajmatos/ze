"""Integration tests for workspace follow-through wiring (Phase 116, User Story 1).

Exercises the settings -> bootstrap.build_workspace_stack -> ze_workspace.tools
boundary end to end (ZeApiSettings-shaped settings, real RunWatcher), with an
in-memory fake WorkspaceStore standing in for Postgres — SQL correctness for the
new store methods is covered by core/ze-workspace/tests/test_store.py.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

import ze_workspace.bootstrap as bootstrap
import ze_workspace.tools as tools
from ze_workspace.types import (
    WorkspaceMode,
    WorkspaceRun,
    WorkspaceRunResult,
)


class FakeInMemoryStore:
    """Minimal WorkspaceStore stand-in — enough surface for workspace_run's path."""

    def __init__(self, mode: WorkspaceMode = WorkspaceMode.AUTO) -> None:
        self._mode = mode
        self.runs: dict = {}

    async def get_mode(self):
        return self._mode

    async def insert_in_progress_run(self, run: WorkspaceRun) -> WorkspaceRun:
        recorded = WorkspaceRun(
            id=uuid4(),
            command=run.command,
            origin=run.origin,
            status=None,
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            thread_id=run.thread_id,
        )
        self.runs[recorded.id] = recorded
        return recorded

    async def complete_run(self, run_id, *, status, exit_code=None, output_preview="",
                            output_file_path=None, files_touched=None, error_summary=None):
        run = self.runs[run_id]
        if run.ended_at is not None:
            return None
        completed = WorkspaceRun(
            id=run.id,
            command=run.command,
            origin=run.origin,
            status=status,
            started_at=run.started_at,
            ended_at=datetime.now(timezone.utc),
            thread_id=run.thread_id,
            exit_code=exit_code,
            output_preview=output_preview,
            error_summary=error_summary,
        )
        self.runs[run_id] = completed
        return completed

    async def list_in_progress(self):
        return [r for r in self.runs.values() if r.ended_at is None]

    async def mark_follow_through_notified(self, run_id) -> bool:
        return True

    async def touch_used(self) -> None:
        pass

    async def insert_run(self, run: WorkspaceRun) -> WorkspaceRun:
        recorded = WorkspaceRun(id=uuid4(), **{
            k: v for k, v in run.__dict__.items() if k != "id"
        })
        self.runs[recorded.id] = recorded
        return recorded


def _settings(short_wait: float) -> SimpleNamespace:
    return SimpleNamespace(
        workspace_service_url="http://ze-workspace.internal:8080",
        workspace_api_token="",
        workspace_timeout_seconds=120,
        workspace_follow_through_short_wait_seconds=short_wait,
        config={"workspace": {}},
    )


def _wire(monkeypatch, *, short_wait: float, run_seconds: float, mode=WorkspaceMode.AUTO):
    store = FakeInMemoryStore(mode)
    monkeypatch.setattr(bootstrap, "PostgresWorkspaceStore", lambda pool: store)
    shared = SimpleNamespace(pool=None)
    stack = bootstrap.build_workspace_stack(shared, _settings(short_wait))

    async def fake_run(*args, **kwargs):
        await asyncio.sleep(run_seconds)
        return WorkspaceRunResult(
            exit_code=0, timed_out=False, stdout_preview="ok", stderr_preview=""
        )

    stack.client.health = AsyncMock(return_value=True)
    stack.client.run = AsyncMock(side_effect=fake_run)
    return stack, store


@pytest.mark.asyncio
async def test_short_run_finishes_in_turn_without_detach(monkeypatch):
    stack, store = _wire(monkeypatch, short_wait=0.05, run_seconds=0.0)
    detach_spy = AsyncMock(wraps=stack.run_watcher.detach)
    monkeypatch.setattr(stack.run_watcher, "detach", detach_spy)

    result = await tools.workspace_run("echo hi")

    assert "ok" in result
    assert "still running" not in result
    detach_spy.assert_not_awaited()
    (run,) = store.runs.values()
    assert run.ended_at is not None
    assert run.status is not None


@pytest.mark.asyncio
async def test_long_run_detaches_and_ends_turn_with_still_running(monkeypatch):
    stack, store = _wire(monkeypatch, short_wait=0.02, run_seconds=0.1)
    detach_spy = AsyncMock(wraps=stack.run_watcher.detach)
    monkeypatch.setattr(stack.run_watcher, "detach", detach_spy)

    result = await tools.workspace_run("sleep 60")

    assert "still running" in result
    detach_spy.assert_awaited_once()
    (run,) = store.runs.values()
    assert run.ended_at is None

    # Let the detached background task finish so it doesn't leak past the test.
    task = stack.run_watcher._tasks.get(run.id)
    if task is not None:
        await task
