from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ze_workspace.store import PostgresWorkspaceStore
from ze_workspace.types import (
    WorkspaceMode,
    WorkspaceRun,
    WorkspaceRunOrigin,
    WorkspaceRunStatus,
)

from tests.conftest import make_pool


def _state_row(mode: str = "ask"):
    now = datetime.now(timezone.utc)
    return {
        "id": 1,
        "mode": mode,
        "last_reset_at": None,
        "last_used_at": None,
        "updated_at": now,
    }


def _run_row(**overrides):
    now = datetime.now(timezone.utc)
    row = {
        "id": uuid4(),
        "started_at": now,
        "ended_at": now,
        "command": "echo hi",
        "origin": "conversation",
        "thread_id": "t1",
        "message_id": None,
        "skill_id": None,
        "skill_script_path": None,
        "status": "succeeded",
        "exit_code": 0,
        "output_preview": "hi",
        "output_file_path": None,
        "files_touched": [],
        "error_summary": None,
    }
    row.update(overrides)
    return row


async def test_get_mode_defaults_to_ask():
    pool, conn = make_pool(fetchrow=_state_row("ask"))
    store = PostgresWorkspaceStore(pool)
    assert await store.get_mode() == WorkspaceMode.ASK


async def test_set_mode_persists():
    pool, conn = make_pool(fetchrow=_state_row("auto"))
    store = PostgresWorkspaceStore(pool)
    state = await store.set_mode(WorkspaceMode.AUTO)
    assert state.mode == WorkspaceMode.AUTO
    sql = conn.fetchrow.await_args.args[0]
    assert "UPDATE workspace_state" in sql
    assert conn.fetchrow.await_args.args[1] == "auto"


async def test_unknown_mode_refused():
    pool, conn = make_pool(fetchrow=_state_row("not-a-mode"))
    store = PostgresWorkspaceStore(pool)
    with pytest.raises(Exception, match="unknown workspace mode"):
        await store.get_mode()


async def test_insert_run_redacts_preview():
    row = _run_row(output_preview="ok")
    pool, conn = make_pool(fetchrow=row)
    store = PostgresWorkspaceStore(pool)
    run = WorkspaceRun(
        command="env",
        origin=WorkspaceRunOrigin.CONVERSATION,
        status=WorkspaceRunStatus.SUCCEEDED,
        output_preview="OPENROUTER_API_KEY=sk-secret",
        error_summary="ZE_API_KEY=abc",
    )
    result = await store.insert_run(run)
    assert result.command == "echo hi"
    args = conn.fetchrow.await_args.args
    assert "OPENROUTER_API_KEY=sk-secret" not in args
    assert any(isinstance(a, str) and "[redacted]" in a for a in args)


async def test_list_runs_filters_origin():
    row = _run_row(origin="unattended")
    pool, conn = make_pool()
    conn.fetch = AsyncMock(return_value=[row])
    store = PostgresWorkspaceStore(pool)
    runs = await store.list_runs(origin=WorkspaceRunOrigin.UNATTENDED)
    assert len(runs) == 1
    assert runs[0].origin == WorkspaceRunOrigin.UNATTENDED
    sql = conn.fetch.await_args.args[0]
    assert "origin" in sql
