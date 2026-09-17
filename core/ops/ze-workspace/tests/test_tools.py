from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ze_agents.errors import ToolConfirmationRequired
from ze_agents.interrupt import workspace_confirmed, workspace_run_origin
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
    WorkspaceRun,
    WorkspaceRunOrigin,
    WorkspaceRunStatusDTO,
)


def _status(**overrides) -> WorkspaceRunStatusDTO:
    base = dict(
        id=uuid4(),
        status="succeeded",
        exit_code=0,
        timed_out=False,
        stdout_preview="ok",
        stderr_preview="",
        output_file_path=None,
        files_touched=[],
    )
    base.update(overrides)
    return WorkspaceRunStatusDTO(**base)


def _store() -> AsyncMock:
    store = AsyncMock()
    store.insert_run = AsyncMock(side_effect=lambda run: run)
    store.insert_in_progress_run = AsyncMock(
        side_effect=lambda run: replace(run, id=uuid4())
    )
    store.complete_run = AsyncMock(side_effect=lambda run_id, **kwargs: SimpleNamespace(id=run_id, **kwargs))
    store.touch_used = AsyncMock()
    store.mark_sidecar_dispatched = AsyncMock(return_value=True)
    store.list_in_progress = AsyncMock(return_value=[])
    return store


def _client() -> AsyncMock:
    client = AsyncMock()
    client.health = AsyncMock(return_value=True)
    client.list_dir = AsyncMock(return_value=[])
    client.download = AsyncMock(return_value=b"hello")
    client.put = AsyncMock(return_value={"path": "notes.txt", "size": 5})
    client.delete = AsyncMock()
    client.start_run = AsyncMock(return_value=None)
    client.get_run = AsyncMock(side_effect=lambda run_id: _status(id=run_id))
    return client


def _wire(client: AsyncMock | None = None, ingestion=None):
    client = client or _client()
    store = _store()
    configure(
        client=client,
        gate=WorkspaceGate(),
        store=store,
        settings=SimpleNamespace(workspace_timeout_seconds=120),
        ingestion_pipeline=ingestion,
    )
    return client, store


async def test_list_returns_files():
    client, _ = _wire()
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


async def test_conversation_write_raises_confirmation():
    _wire()
    with pytest.raises(ToolConfirmationRequired) as exc:
        await workspace_write("notes.txt", "secret")
    assert exc.value.proposed == "secret"
    assert exc.value.editable is True


async def test_conversation_run_raises_confirmation():
    _wire()
    with pytest.raises(ToolConfirmationRequired):
        await workspace_run("rm -rf /")


async def test_unattended_run_executes_and_persists():
    client, store = _wire()
    token = workspace_run_origin.set("unattended")
    try:
        result = await workspace_run("echo hi")
    finally:
        workspace_run_origin.reset(token)
    assert "ok" in result
    client.start_run.assert_awaited_once()
    store.insert_in_progress_run.assert_awaited_once()
    store.complete_run.assert_awaited_once()


async def test_truncated_output_mentions_spill_path():
    client, _ = _wire()
    client.get_run = AsyncMock(
        side_effect=lambda run_id: _status(
            id=run_id,
            stdout_preview="head",
            output_file_path=".ze-output/run-1.txt",
        )
    )
    token = workspace_confirmed.set(True)
    try:
        result = await workspace_run("yes")
    finally:
        workspace_confirmed.reset(token)
    assert ".ze-output/run-1.txt" in result


async def test_read_and_delete():
    client, _ = _wire()
    assert await workspace_read("a.txt") == "hello"
    token = workspace_confirmed.set(True)
    try:
        assert "Deleted" in await workspace_delete("a.txt")
    finally:
        workspace_confirmed.reset(token)
    client.download.assert_awaited_once()
    client.delete.assert_awaited_once()


async def test_ingest_uses_injected_pipeline_and_does_not_delete():
    pipeline = SimpleNamespace(ingest=AsyncMock(return_value=SimpleNamespace(facts_count=2)))
    client, _ = _wire(ingestion=pipeline)
    token = workspace_confirmed.set(True)
    try:
        result = await ingest_workspace_file("notes.txt")
    finally:
        workspace_confirmed.reset(token)
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
    client, _ = _wire()
    configure(
        client=client,
        gate=WorkspaceGate(),
        store=_store(),
        skill_store=store,
    )
    result = await workspace_run_skill_script(skill_id, "scripts/h.py")
    assert "separately approved" in result
    client.start_run.assert_not_awaited()


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
    client, ws_store = _wire()
    configure(
        client=client,
        gate=WorkspaceGate(),
        store=ws_store,
        skill_store=store,
        settings=SimpleNamespace(workspace_timeout_seconds=120),
    )
    token = workspace_confirmed.set(True)
    try:
        result = await workspace_run_skill_script(str(skill_uuid), "scripts/h.py")
    finally:
        workspace_confirmed.reset(token)
    client.put.assert_awaited()
    put_args = client.put.await_args
    assert put_args.args[1] == b"print(1)"
    client.start_run.assert_awaited_once()
    assert "ok" in result


async def test_run_skill_script_raises_confirmation():
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
    client, ws_store = _wire()
    configure(
        client=client,
        gate=WorkspaceGate(),
        store=ws_store,
        skill_store=store,
    )
    with pytest.raises(ToolConfirmationRequired):
        await workspace_run_skill_script(skill_id, "scripts/h.py")
    client.start_run.assert_not_awaited()


async def test_unavailable_sidecar_raises():
    client, _ = _wire()
    client.health = AsyncMock(return_value=False)
    with pytest.raises(WorkspaceUnavailableError):
        await workspace_list("")


async def test_conversation_run_does_not_detach_before_confirm():
    run_watcher = AsyncMock()
    client, store = _wire()
    configure(client=client, gate=WorkspaceGate(), store=store, run_watcher=run_watcher)
    with pytest.raises(ToolConfirmationRequired):
        await workspace_run("echo hi")
    run_watcher.detach.assert_not_awaited()


async def test_ask_run_detaches_only_after_confirmation_resume():
    import time

    run_watcher = AsyncMock()
    client = _client()
    run_started_at: dict = {}

    async def slow_get_run(run_id):
        started = run_started_at.setdefault(run_id, time.monotonic())
        if time.monotonic() - started >= 0.05:
            return _status(id=run_id)
        return _status(id=run_id, status="running", exit_code=None)

    client.get_run = AsyncMock(side_effect=slow_get_run)
    store = _store()
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


def _in_progress_run() -> WorkspaceRun:
    return WorkspaceRun(
        id=uuid4(),
        command="sleep 60",
        origin=WorkspaceRunOrigin.CONVERSATION,
        status=None,
        thread_id="t1",
    )


@pytest.mark.parametrize(
    "origin",
    [WorkspaceRunOrigin.CONVERSATION, WorkspaceRunOrigin.USER, WorkspaceRunOrigin.UNATTENDED],
)
async def test_workspace_run_refuses_while_another_run_in_progress(origin):
    running = _in_progress_run()
    client, store = _wire()
    store.list_in_progress = AsyncMock(return_value=[running])
    confirm = workspace_confirmed.set(True) if origin is WorkspaceRunOrigin.CONVERSATION else None
    token = workspace_run_origin.set(origin.value)
    try:
        result = await workspace_run("echo hi")
    finally:
        workspace_run_origin.reset(token)
        if confirm is not None:
            workspace_confirmed.reset(confirm)
    if origin is WorkspaceRunOrigin.USER:
        assert "not allowed" in result.lower()
        client.start_run.assert_not_awaited()
        return
    assert str(running.id) in result
    assert running.command in result
    client.start_run.assert_not_awaited()


async def test_workspace_run_skill_script_refuses_while_another_run_in_progress():
    running = _in_progress_run()
    skill_id = "11111111-1111-1111-1111-111111111111"
    skill_store = AsyncMock()
    skill_store.get = AsyncMock(
        return_value=SimpleNamespace(
            id=skill_id,
            name="S",
            status=SimpleNamespace(value="active"),
            has_scripts=True,
            executable_approved=True,
        )
    )
    skill_store.get_script = AsyncMock(
        return_value=SimpleNamespace(filename="scripts/h.py", content=b"print(1)")
    )
    client = _client()
    store = _store()
    store.list_in_progress = AsyncMock(return_value=[running])
    configure(client=client, gate=WorkspaceGate(), store=store, skill_store=skill_store)

    token = workspace_confirmed.set(True)
    try:
        result = await workspace_run_skill_script(skill_id, "scripts/h.py")
    finally:
        workspace_confirmed.reset(token)

    assert str(running.id) in result
    client.put.assert_not_awaited()
    client.start_run.assert_not_awaited()
