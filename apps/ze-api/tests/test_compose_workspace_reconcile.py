"""Regression test for reconcile_in_progress_workspace_runs (Phase 129 T019) —
every ended_at IS NULL row found at startup must be handed to
RunWatcher.reattach() exactly once."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ze_api.compose import reconcile_in_progress_workspace_runs
from ze_workspace.types import WorkspaceRun, WorkspaceRunOrigin


def _in_progress_run() -> WorkspaceRun:
    return WorkspaceRun(
        id=uuid4(),
        command="sleep 60",
        origin=WorkspaceRunOrigin.CONVERSATION,
        status=None,
        started_at=datetime.now(timezone.utc),
        ended_at=None,
        thread_id="t1",
    )


@pytest.mark.asyncio
async def test_reconcile_reattaches_every_in_progress_run():
    runs = [_in_progress_run(), _in_progress_run()]
    store = AsyncMock()
    store.list_in_progress = AsyncMock(return_value=runs)
    run_watcher = AsyncMock()

    await reconcile_in_progress_workspace_runs(store, run_watcher)

    assert run_watcher.reattach.await_count == 2
    reattached_ids = {call.args[0].id for call in run_watcher.reattach.await_args_list}
    assert reattached_ids == {r.id for r in runs}


@pytest.mark.asyncio
async def test_reconcile_survives_one_reattach_failure():
    runs = [_in_progress_run(), _in_progress_run()]
    store = AsyncMock()
    store.list_in_progress = AsyncMock(return_value=runs)
    run_watcher = AsyncMock()
    run_watcher.reattach = AsyncMock(side_effect=[RuntimeError("boom"), None])

    await reconcile_in_progress_workspace_runs(store, run_watcher)

    assert run_watcher.reattach.await_count == 2
