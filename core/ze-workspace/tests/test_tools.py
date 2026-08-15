from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ze_agents.errors import ToolConfirmationRequired
from ze_agents.interrupt import workspace_confirmed
from ze_workspace.errors import WorkspaceUnavailableError
from ze_workspace.gate import WorkspaceGate
from ze_workspace.tools import (
    configure,
    ingest_workspace_file,
    workspace_delete,
    workspace_list,
    workspace_read,
    workspace_run,
    workspace_run_skill_script,
    workspace_write,
)
from ze_workspace.types import (
    WorkspaceFile,
    WorkspaceMode,
    WorkspaceRunResult,
)


def _store(mode: WorkspaceMode) -> AsyncMock:
    store = AsyncMock()
    store.get_mode = AsyncMock(return_value=mode)
    store.insert_run = AsyncMock(side_effect=lambda run: run)
    store.insert_in_progress_run = AsyncMock(
        side_effect=lambda run: replace(run, id=uuid4())
    )
    store.complete_run = AsyncMock(side_effect=lambda run_id, **kwargs: SimpleNamespace(id=run_id, **kwargs))
    store.touch_used = AsyncMock()
    return store


def _client() -> AsyncMock:
    client = AsyncMock()
    client.health = AsyncMock(return_value=True)
    client.list_dir = AsyncMock(return_value=[])
    client.download = AsyncMock(return_value=b"hello")
    client.put = AsyncMock(return_value={"path": "notes.txt", "size": 5})
    client.delete = AsyncMock()
    client.run = AsyncMock(
        return_value=WorkspaceRunResult(
            exit_code=0,
            timed_out=False,
            stdout_preview="ok",
            stderr_preview="",
        )
    )
    return client


def _wire(mode: WorkspaceMode, client: AsyncMock | None = None, ingestion=None):
    client = client or _client()
    store = _store(mode)
    configure(
        client=client,
        gate=WorkspaceGate(),
        store=store,
        settings=SimpleNamespace(workspace_timeout_seconds=120),
        ingestion_pipeline=ingestion,
    )
    return client, store


async def test_list_returns_files():
    client, _ = _wire(WorkspaceMode.ASK)
    client.list_dir = AsyncMock(
        return_value=[
            WorkspaceFile(
                path="a.txt",
                size=3,
                modified_at=datetime.now(timezone.utc),
                is_dir=False,
            )
        ]
    )
    result = await workspace_list("")
    assert "a.txt" in result
    client.list_dir.assert_awaited_once()


async def test_off_denies_list_without_calling_client():
    client, _ = _wire(WorkspaceMode.OFF)
    result = await workspace_list("")
    assert "off" in result
    client.list_dir.assert_not_awaited()


async def test_plan_write_is_dry_run():
    client, store = _wire(WorkspaceMode.PLAN)
    result = await workspace_write("notes.txt", "hi")
    assert result.startswith("[plan]")
    client.put.assert_not_awaited()
    store.insert_run.assert_not_awaited()


async def test_plan_run_is_dry_run():
    client, _ = _wire(WorkspaceMode.PLAN)
    result = await workspace_run("echo hi")
    assert "[plan]" in result
    client.run.assert_not_awaited()


async def test_ask_write_raises_confirmation():
    _wire(WorkspaceMode.ASK)
    with pytest.raises(ToolConfirmationRequired) as exc:
        await workspace_write("notes.txt", "secret")
    assert exc.value.proposed == "secret"
    assert exc.value.editable is True


async def test_ask_run_raises_confirmation():
    _wire(WorkspaceMode.ASK)
    with pytest.raises(ToolConfirmationRequired):
        await workspace_run("rm -rf /")


async def test_auto_edit_write_executes_without_confirm():
    client, _ = _wire(WorkspaceMode.AUTO_EDIT)
    result = await workspace_write("notes.txt", "hi")
    assert "Wrote" in result
    client.put.assert_awaited_once()


async def test_auto_edit_run_still_confirms():
    client, _ = _wire(WorkspaceMode.AUTO_EDIT)
    with pytest.raises(ToolConfirmationRequired):
        await workspace_run("echo hi")
    client.run.assert_not_awaited()


async def test_auto_run_executes_and_persists():
    client, store = _wire(WorkspaceMode.AUTO)
    result = await workspace_run("echo hi")
    assert "ok" in result
    client.run.assert_awaited_once()
    store.insert_in_progress_run.assert_awaited_once()
    store.complete_run.assert_awaited_once()


async def test_truncated_output_mentions_spill_path():
    client, _ = _wire(WorkspaceMode.AUTO)
    client.run = AsyncMock(
        return_value=WorkspaceRunResult(
            exit_code=0,
            timed_out=False,
            stdout_preview="head",
            stderr_preview="",
            output_file_path=".ze-output/run-1.txt",
        )
    )
    result = await workspace_run("yes")
    assert ".ze-output/run-1.txt" in result


async def test_read_and_delete():
    client, _ = _wire(WorkspaceMode.AUTO)
    assert await workspace_read("a.txt") == "hello"
    assert "Deleted" in await workspace_delete("a.txt")
    client.download.assert_awaited_once()
    client.delete.assert_awaited_once()


async def test_ingest_uses_injected_pipeline_and_does_not_delete():
    pipeline = SimpleNamespace(ingest=AsyncMock(return_value=SimpleNamespace(facts_count=2)))
    client, _ = _wire(WorkspaceMode.AUTO, ingestion=pipeline)
    result = await ingest_workspace_file("notes.txt")
    assert "Ingested" in result
    assert "not deleted" in result.lower()
    pipeline.ingest.assert_awaited_once()
    req = pipeline.ingest.await_args.args[0]
    assert req.file_bytes == b"hello"
    assert req.label == "notes.txt"
    client.delete.assert_not_awaited()


async def test_run_skill_script_refuses_without_executable_approval():
    skill_id = "11111111-1111-1111-1111-111111111111"
    store = AsyncMock()
    store.get = AsyncMock(
        return_value=SimpleNamespace(
            id=skill_id,
            name="S",
            status=SimpleNamespace(value="active"),
            has_scripts=True,
            executable_approved=False,
        )
    )
    client, _ = _wire(WorkspaceMode.AUTO)
    configure(
        client=client,
        gate=WorkspaceGate(),
        store=_store(WorkspaceMode.AUTO),
        skill_store=store,
    )
    result = await workspace_run_skill_script(skill_id, "scripts/h.py")
    assert "separately approved" in result
    client.run.assert_not_awaited()


async def test_run_skill_script_auto_materializes_from_db_bytes():
    from uuid import UUID

    skill_uuid = UUID("11111111-1111-1111-1111-111111111111")
    store = AsyncMock()
    store.get = AsyncMock(
        return_value=SimpleNamespace(
            id=skill_uuid,
            name="S",
            status=SimpleNamespace(value="active"),
            has_scripts=True,
            executable_approved=True,
        )
    )
    store.get_script = AsyncMock(
        return_value=SimpleNamespace(filename="scripts/h.py", content=b"print(1)")
    )
    client, ws_store = _wire(WorkspaceMode.AUTO)
    configure(
        client=client,
        gate=WorkspaceGate(),
        store=ws_store,
        skill_store=store,
        settings=SimpleNamespace(workspace_timeout_seconds=120),
    )
    result = await workspace_run_skill_script(str(skill_uuid), "scripts/h.py")
    client.put.assert_awaited()
    put_args = client.put.await_args
    assert put_args.args[1] == b"print(1)"
    client.run.assert_awaited_once()
    assert "ok" in result


async def test_run_skill_script_off_does_not_execute():
    skill_id = "11111111-1111-1111-1111-111111111111"
    store = AsyncMock()
    store.get = AsyncMock(
        return_value=SimpleNamespace(
            id=skill_id,
            name="S",
            status=SimpleNamespace(value="active"),
            has_scripts=True,
            executable_approved=True,
        )
    )
    store.get_script = AsyncMock(
        return_value=SimpleNamespace(filename="scripts/h.py", content=b"print(1)")
    )
    client, _ = _wire(WorkspaceMode.OFF)
    configure(
        client=client,
        gate=WorkspaceGate(),
        store=_store(WorkspaceMode.OFF),
        skill_store=store,
    )
    result = await workspace_run_skill_script(skill_id, "scripts/h.py")
    assert "off" in result.lower()
    client.run.assert_not_awaited()
    client.put.assert_not_awaited()


async def test_run_skill_script_plan_is_dry_run():
    skill_id = "11111111-1111-1111-1111-111111111111"
    store = AsyncMock()
    store.get = AsyncMock(
        return_value=SimpleNamespace(
            id=skill_id,
            name="S",
            status=SimpleNamespace(value="active"),
            has_scripts=True,
            executable_approved=True,
        )
    )
    store.get_script = AsyncMock(
        return_value=SimpleNamespace(filename="scripts/h.py", content=b"print(1)")
    )
    client, _ = _wire(WorkspaceMode.PLAN)
    configure(
        client=client,
        gate=WorkspaceGate(),
        store=_store(WorkspaceMode.PLAN),
        skill_store=store,
    )
    result = await workspace_run_skill_script(skill_id, "scripts/h.py")
    assert "[plan]" in result
    client.run.assert_not_awaited()


async def test_run_skill_script_ask_raises_confirmation():
    skill_id = "11111111-1111-1111-1111-111111111111"
    store = AsyncMock()
    store.get = AsyncMock(
        return_value=SimpleNamespace(
            id=skill_id,
            name="S",
            status=SimpleNamespace(value="active"),
            has_scripts=True,
            executable_approved=True,
        )
    )
    store.get_script = AsyncMock(
        return_value=SimpleNamespace(filename="scripts/h.py", content=b"print(1)")
    )
    client, ws_store = _wire(WorkspaceMode.ASK)
    configure(
        client=client,
        gate=WorkspaceGate(),
        store=ws_store,
        skill_store=store,
    )
    with pytest.raises(ToolConfirmationRequired):
        await workspace_run_skill_script(skill_id, "scripts/h.py")
    client.run.assert_not_awaited()


async def test_unavailable_sidecar_raises():
    client, _ = _wire(WorkspaceMode.AUTO)
    client.health = AsyncMock(return_value=False)
    with pytest.raises(WorkspaceUnavailableError):
        await workspace_list("")


async def test_off_and_plan_never_reach_run_watcher():
    run_watcher = AsyncMock()

    client, store = _wire(WorkspaceMode.OFF)
    configure(client=client, gate=WorkspaceGate(), store=store, run_watcher=run_watcher)
    await workspace_run("echo hi")
    run_watcher.detach.assert_not_awaited()

    client, store = _wire(WorkspaceMode.PLAN)
    configure(client=client, gate=WorkspaceGate(), store=store, run_watcher=run_watcher)
    await workspace_run("echo hi")
    run_watcher.detach.assert_not_awaited()


async def test_ask_run_detaches_only_after_confirmation_resume():
    run_watcher = AsyncMock()
    client = _client()

    async def slow_run(*args, **kwargs):
        await asyncio.sleep(0.05)
        return WorkspaceRunResult(
            exit_code=0, timed_out=False, stdout_preview="ok", stderr_preview=""
        )

    client.run = AsyncMock(side_effect=slow_run)
    store = _store(WorkspaceMode.ASK)
    configure(
        client=client,
        gate=WorkspaceGate(),
        store=store,
        settings=SimpleNamespace(
            workspace_timeout_seconds=120,
            workspace_follow_through_short_wait_seconds=0.01,
        ),
        run_watcher=run_watcher,
    )
    with pytest.raises(ToolConfirmationRequired):
        await workspace_run("echo hi")
    run_watcher.detach.assert_not_awaited()

    token = workspace_confirmed.set(True)
    try:
        result = await workspace_run("echo hi")
    finally:
        workspace_confirmed.reset(token)
    assert "still running" in result
    run_watcher.detach.assert_awaited_once()
