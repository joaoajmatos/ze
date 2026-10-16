from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

from ze_workspace.client import WorkspaceClient
from ze_workspace.errors import (
    WorkspaceBusyError,
    WorkspaceFullError,
    WorkspaceNotFoundError,
    WorkspacePathError,
    WorkspaceRunAlreadyTerminalError,
    WorkspaceUnavailableError,
)
from ze_workspace.store import WorkspaceStore
from ze_workspace.types import WorkspaceRunOrigin

_ERROR_STATUS = {
    WorkspaceUnavailableError: 503,
    WorkspaceBusyError: 409,
    WorkspaceFullError: 409,
    WorkspacePathError: 400,
    WorkspaceNotFoundError: 404,
    WorkspaceRunAlreadyTerminalError: 409,
}


def http_status_for(exc: Exception) -> int:
    for cls, status in _ERROR_STATUS.items():
        if isinstance(exc, cls):
            return status
    return 500


def _run_to_dict(run) -> dict:
    return {
        "id": str(run.id) if run.id else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "command": run.command,
        "origin": run.origin.value,
        "thread_id": run.thread_id,
        "message_id": str(run.message_id) if run.message_id else None,
        "skill_id": str(run.skill_id) if run.skill_id else None,
        "skill_script_path": run.skill_script_path,
        "status": run.status.value if run.status is not None else "in_progress",
        "exit_code": run.exit_code,
        "output_preview": run.output_preview,
        "output_file_path": run.output_file_path,
        "files_touched": [{"path": t.path, "op": t.op} for t in run.files_touched],
        "error_summary": run.error_summary,
        "follow_through_notified": run.follow_through_notified,
    }


async def get_status(store: WorkspaceStore, client: WorkspaceClient) -> dict:
    state = await store.get_state()
    available = await client.health()
    bytes_used = 0
    bytes_ceiling = 1073741824
    busy = False
    if available:
        try:
            stat = await client.stat()
            bytes_used = stat.bytes_used
            bytes_ceiling = stat.bytes_ceiling
            busy = stat.busy
        except WorkspaceUnavailableError:
            available = False
    return {
        "available": available,
        "bytes_used": bytes_used,
        "bytes_ceiling": bytes_ceiling,
        "busy": busy,
        "last_reset_at": state.last_reset_at.isoformat()
        if state.last_reset_at
        else None,
        "last_used_at": state.last_used_at.isoformat() if state.last_used_at else None,
    }


async def list_files(client: WorkspaceClient, path: str = "") -> dict:
    files = await client.list_dir(path)
    return {
        "files": [
            {
                "path": f.path,
                "size": f.size,
                "modified_at": f.modified_at.isoformat(),
                "is_dir": f.is_dir,
            }
            for f in files
        ]
    }


async def download_file(client: WorkspaceClient, path: str) -> bytes:
    return await client.download(path)


async def cancel_run(
    store: WorkspaceStore,
    client: WorkspaceClient,
    run_watcher: Any,
    run_id: UUID,
) -> dict:
    """User Story 3: stop an in-progress run without a confirmation prompt
    (FR-009 — never routes through WorkspaceGate.decide()). Raises
    WorkspaceNotFoundError for an unknown id, WorkspaceRunAlreadyTerminalError
    if the run already finished (route layer maps both to their HTTP status via
    http_status_for)."""
    run = await store.get_run(run_id)
    if run is None:
        raise WorkspaceNotFoundError(f"workspace run {run_id} not found")
    if run.ended_at is not None:
        raise WorkspaceRunAlreadyTerminalError("already finished")
    try:
        await client.cancel_run(run_id)
    except (WorkspaceNotFoundError, WorkspaceRunAlreadyTerminalError):
        pass
    cancelled = await run_watcher.cancel(run_id)
    if cancelled is None:
        raise WorkspaceRunAlreadyTerminalError("already finished")
    return _run_to_dict(cancelled)


def _unique_name(existing: set[str], path: str) -> str:
    if path not in existing:
        return path
    p = PurePosixPath(path)
    stem, suffix, parent = p.stem or "file", p.suffix, str(p.parent)
    n = 1
    while True:
        name = f"{stem}-{n}{suffix}"
        candidate = name if parent in {".", ""} else f"{parent}/{name}"
        if candidate not in existing:
            return candidate
        n += 1


async def upload_file(
    client: WorkspaceClient, filename: str, content: bytes, dest: str | None = None
) -> dict:
    requested = dest or filename
    listing = await client.list_dir("")
    existing = {f.path for f in listing}
    stored = _unique_name(existing, requested)
    result = await client.upload(stored, content, stored)
    path = result.get("path") or stored
    return {
        "path": path,
        "requested_path": requested,
        "size": result.get("size") or len(content),
        "deduplicated": path != requested,
    }


async def delete_file(client: WorkspaceClient, path: str) -> None:
    await client.delete(path)


async def list_runs(
    store: WorkspaceStore,
    *,
    limit: int = 50,
    origin: str | None = None,
) -> dict:
    origin_enum = WorkspaceRunOrigin(origin) if origin else None
    runs = await store.list_runs(limit=limit, origin=origin_enum)
    return {"runs": [_run_to_dict(r) for r in runs]}
