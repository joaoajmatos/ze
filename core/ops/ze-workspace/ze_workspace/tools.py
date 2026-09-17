"""Workspace platform tools. Consult WorkspaceGate; never auto-ingest on write/place."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from ze_agents.errors import ToolConfirmationRequired
from ze_agents.interrupt import (
    workspace_confirmed,
    workspace_run_origin,
    workspace_thread_id,
)
from ze_agents.tool import ToolAccess, tool
from ze_logging import get_logger

from ze_workspace.errors import WorkspaceUnavailableError
from ze_workspace.sanitize import redact
from ze_workspace.types import (
    WorkspaceAction,
    WorkspaceFileTouch,
    WorkspaceGateDecision,
    WorkspaceRun,
    WorkspaceRunOrigin,
    WorkspaceRunStatus,
    WorkspaceRunStatusDTO,
)

_POLL_MIN_INTERVAL_SECONDS = 0.005
_POLL_MAX_INTERVAL_SECONDS = 0.05

DEFAULT_SHORT_WAIT_SECONDS = 25.0

log = get_logger(__name__)

WORKSPACE_TOOLS = [
    "workspace_list",
    "workspace_read",
    "workspace_write",
    "workspace_delete",
    "workspace_run",
    "workspace_run_skill_script",
    "ingest_workspace_file",
    "workspace_reset",
]

_client: Any = None
_gate: Any = None
_store: Any = None
_settings: Any = None
_ingestion: Any = None


_skill_store: Any = None
_run_watcher: Any = None
_short_wait_seconds: float = DEFAULT_SHORT_WAIT_SECONDS


def configure(
    *,
    client: Any,
    gate: Any,
    store: Any,
    settings: Any = None,
    ingestion_pipeline: Any = None,
    skill_store: Any = None,
    run_watcher: Any = None,
) -> None:
    global _client, _gate, _store, _settings, _ingestion, _skill_store
    global _run_watcher, _short_wait_seconds
    _client = client
    _gate = gate
    _store = store
    _settings = settings
    if ingestion_pipeline is not None:
        _ingestion = ingestion_pipeline
    if skill_store is not None:
        _skill_store = skill_store
    if run_watcher is not None:
        _run_watcher = run_watcher
    if settings is not None:
        _short_wait_seconds = float(
            getattr(settings, "workspace_follow_through_short_wait_seconds", None)
            or DEFAULT_SHORT_WAIT_SECONDS
        )


async def _ensure_client() -> Any:
    if _client is None:
        raise WorkspaceUnavailableError("workspace is not configured")
    if not await _client.health():
        raise WorkspaceUnavailableError("workspace sidecar is unavailable")
    return _client


async def _decide(
    action: WorkspaceAction,
    origin: WorkspaceRunOrigin | None = None,
) -> WorkspaceGateDecision:
    if _gate is None:
        raise WorkspaceUnavailableError("workspace is not configured")
    if origin is None:
        origin = WorkspaceRunOrigin(workspace_run_origin.get())
    return _gate.decide(action=action, origin=origin)


def _confirm(prompt: str, proposed: str, *, editable: bool = True) -> None:
    if workspace_confirmed.get():
        return
    raise ToolConfirmationRequired(prompt, editable=editable, proposed=proposed)


async def _record_run(
    *,
    command: str,
    origin: WorkspaceRunOrigin,
    status: WorkspaceRunStatus,
    exit_code: int | None = None,
    output_preview: str = "",
    output_file_path: str | None = None,
    files_touched: list[WorkspaceFileTouch] | None = None,
    error_summary: str | None = None,
    skill_id: UUID | None = None,
    skill_script_path: str | None = None,
    thread_id: str | None = None,
) -> WorkspaceRun | None:
    if _store is None:
        return None
    now = datetime.now(timezone.utc)
    run = WorkspaceRun(
        command=command,
        origin=origin,
        status=status,
        started_at=now,
        ended_at=now,
        exit_code=exit_code,
        output_preview=redact(output_preview),
        output_file_path=output_file_path,
        files_touched=files_touched or [],
        error_summary=redact(error_summary) if error_summary else None,
        skill_id=skill_id,
        skill_script_path=skill_script_path,
        thread_id=thread_id,
    )
    recorded = await _store.insert_run(run)
    if status is not WorkspaceRunStatus.REFUSED:
        await _store.touch_used()
    return recorded


def _format_status_output(status: WorkspaceRunStatusDTO) -> str:
    parts = [status.stdout_preview or ""]
    if status.stderr_preview:
        parts.append(status.stderr_preview)
    if status.output_file_path:
        parts.append(f"(full output spilled to {status.output_file_path})")
    if status.timed_out:
        parts.append("(timed out)")
    return "\n".join(p for p in parts if p) or f"exit {status.exit_code}"


_STATUS_MAP = {
    "succeeded": WorkspaceRunStatus.SUCCEEDED,
    "failed": WorkspaceRunStatus.FAILED,
    "timed_out": WorkspaceRunStatus.TIMED_OUT,
    "cancelled": WorkspaceRunStatus.CANCELLED,
}


async def _poll_get_run(
    run_id: UUID, deadline_seconds: float | None
) -> WorkspaceRunStatusDTO | None:
    """Polls client.get_run(run_id) until it reports a terminal status or
    deadline_seconds elapses. deadline_seconds=None polls with no time bound
    (used only when no WorkspaceStore is configured — see _run_and_maybe_detach).
    Returns None if the deadline elapsed while still running."""
    loop = asyncio.get_event_loop()
    start = loop.time()
    interval = _POLL_MAX_INTERVAL_SECONDS
    if deadline_seconds is not None:
        interval = min(
            _POLL_MAX_INTERVAL_SECONDS,
            max(deadline_seconds / 10, _POLL_MIN_INTERVAL_SECONDS),
        )
    while True:
        status = await _client.get_run(run_id)
        if status is not None and status.status != "running":
            return status
        if deadline_seconds is not None and loop.time() - start >= deadline_seconds:
            return None
        await asyncio.sleep(interval)


async def _refusal_if_busy() -> str | None:
    """FR-007: refuse a second workspace command while one is in progress,
    naming the running handle and command — checked before any sidecar call
    (research.md Decision 5). Applies uniformly to every WorkspaceRunOrigin."""
    if _store is None:
        return None
    in_progress = await _store.list_in_progress()
    if not in_progress:
        return None
    running = in_progress[0]
    return (
        f"Another workspace command is already running: `{running.command}` "
        f"(run {running.id}). Wait for it to finish or cancel it before "
        "starting a new one."
    )


async def _run_and_maybe_detach(
    *,
    command: str,
    origin: WorkspaceRunOrigin,
    argv: list[str],
    timeout_seconds: int,
    skill_id: UUID | None = None,
    skill_script_path: str | None = None,
) -> str:
    """Starts argv via client.start_run (returns immediately, FR-001) and
    polls client.get_run up to _short_wait_seconds. If it finishes in time,
    persists the terminal result and returns the formatted output. If it does
    not, hands the run to the RunWatcher to watch to completion and returns a
    "still running" reply instead of blocking the turn."""
    if _store is None:
        run_id = uuid4()
        await _client.start_run(argv, run_id, timeout_seconds=timeout_seconds)
        status = await _poll_get_run(run_id, deadline_seconds=None)
        return _format_status_output(status) if status else f"exit unknown ({run_id})"

    thread_id = (
        workspace_thread_id.get() if origin is WorkspaceRunOrigin.CONVERSATION else None
    )
    recorded = await _store.insert_in_progress_run(
        WorkspaceRun(
            command=command,
            origin=origin,
            thread_id=thread_id,
            skill_id=skill_id,
            skill_script_path=skill_script_path,
        )
    )
    await _client.start_run(argv, recorded.id, timeout_seconds=timeout_seconds)
    await _store.mark_sidecar_dispatched(recorded.id)

    status = await _poll_get_run(recorded.id, deadline_seconds=_short_wait_seconds)
    if status is None:
        if _run_watcher is not None:
            await _run_watcher.detach(recorded)
        wait_s = int(_short_wait_seconds)
        return (
            f"[still running] run {recorded.id}: `{command}` is taking longer than "
            f"{wait_s}s and is continuing in the background. "
            "I'll follow up on this thread once it finishes."
        )

    await _store.complete_run(
        recorded.id,
        status=_STATUS_MAP[status.status],
        exit_code=status.exit_code,
        output_preview=status.stdout_preview or status.stderr_preview or "",
        output_file_path=status.output_file_path,
        files_touched=status.files_touched,
        error_summary=status.stderr_preview if status.exit_code else None,
    )
    await _store.touch_used()
    return _format_status_output(status)


@tool(
    access=ToolAccess.READ,
    description="List files in the workspace directory. Path is relative to the workspace root.",
)
async def workspace_list(path: str = "") -> str:
    decision = await _decide(WorkspaceAction.LIST)
    if decision is WorkspaceGateDecision.DENY:
        return "Listing the workspace is not allowed."
    client = await _ensure_client()
    files = await client.list_dir(path)
    if not files:
        return "(empty)"
    lines = []
    for f in files:
        kind = "dir" if f.is_dir else "file"
        lines.append(f"{f.path}\t{kind}\t{f.size}")
    return "\n".join(lines)


@tool(
    access=ToolAccess.READ,
    description="Read a text file from the workspace. Path is relative to the workspace root.",
)
async def workspace_read(path: str) -> str:
    decision = await _decide(WorkspaceAction.READ)
    if decision is WorkspaceGateDecision.DENY:
        return "Reading the workspace is not allowed."
    client = await _ensure_client()
    data = await client.download(path)
    return data.decode("utf-8", errors="replace")


@tool(
    access=ToolAccess.WRITE,
    description="Write a text file in the workspace. Path is relative to the workspace root.",
)
async def workspace_write(path: str, content: str) -> str:
    decision = await _decide(WorkspaceAction.WRITE)
    if decision is WorkspaceGateDecision.DENY:
        return "Writing to the workspace is not allowed."
    if decision is WorkspaceGateDecision.CONFIRM:
        _confirm(
            f"Write file {path} ({len(content)} characters) in the workspace?",
            content,
        )
    client = await _ensure_client()
    result = await client.put(path, content.encode("utf-8"), overwrite=True)
    stored = result.get("path") or path
    await _store.touch_used()
    return f"Wrote {stored} ({result.get('size', len(content))} bytes)"


@tool(
    access=ToolAccess.WRITE,
    description="Delete a file or directory in the workspace.",
)
async def workspace_delete(path: str) -> str:
    decision = await _decide(WorkspaceAction.DELETE)
    if decision is WorkspaceGateDecision.DENY:
        return "Deleting from the workspace is not allowed."
    if decision is WorkspaceGateDecision.CONFIRM:
        _confirm(
            f"Delete {path} from the workspace?",
            path,
        )
    client = await _ensure_client()
    await client.delete(path)
    await _store.touch_used()
    return f"Deleted {path}"


@tool(
    access=ToolAccess.WRITE,
    description="Run a shell command in the workspace. Command is a single string executed via bash -lc.",
)
async def workspace_run(command: str) -> str:
    decision = await _decide(WorkspaceAction.RUN)
    if decision is WorkspaceGateDecision.DENY:
        await _record_run(
            command=command,
            origin=WorkspaceRunOrigin(workspace_run_origin.get()),
            status=WorkspaceRunStatus.REFUSED,
            error_summary="command refused",
        )
        return "Running commands in the workspace is not allowed."
    if decision is WorkspaceGateDecision.CONFIRM:
        _confirm(
            f"Run in the workspace: {command}",
            command,
        )
    refusal = await _refusal_if_busy()
    if refusal is not None:
        return refusal
    await _ensure_client()
    timeout = 120
    if _settings is not None:
        timeout = int(getattr(_settings, "workspace_timeout_seconds", 120) or 120)
    origin = WorkspaceRunOrigin(workspace_run_origin.get())
    return await _run_and_maybe_detach(
        command=command,
        origin=origin,
        argv=["bash", "-lc", command],
        timeout_seconds=timeout,
    )


@tool(
    access=ToolAccess.WRITE,
    description=(
        "Run an approved bundled skill script in the workspace. "
        "Requires the skill to be active with executable approval."
    ),
)
async def workspace_run_skill_script(skill_id: str, filename: str) -> str:
    if _skill_store is None:
        return "Skill store is not available."
    try:
        skill = await _skill_store.get(UUID(skill_id))
    except Exception:
        skill = None
    if skill is None:
        return f"Skill {skill_id} was not found."
    status = getattr(skill.status, "value", skill.status)
    if status != "active":
        return f"Skill {getattr(skill, 'name', skill_id)} is not active; scripts will not run."
    if not getattr(skill, "executable_approved", False):
        return (
            "Skill scripts are not executable until separately approved. "
            f"Refusing {filename} on skill {skill_id}."
        )
    if not getattr(skill, "has_scripts", False):
        return f"Skill {skill_id} has no scripts."
    script = await _skill_store.get_script(skill.id, filename)
    if script is None:
        return f"Script {filename} was not found on skill {skill_id}."

    decision = await _decide(WorkspaceAction.RUN_SCRIPT)
    if decision is WorkspaceGateDecision.DENY:
        await _record_run(
            command=f"skill-script {filename}",
            origin=WorkspaceRunOrigin(workspace_run_origin.get()),
            status=WorkspaceRunStatus.REFUSED,
            error_summary="skill script refused",
            skill_id=skill.id,
            skill_script_path=filename,
        )
        return "Running skill scripts in the workspace is not allowed."
    if decision is WorkspaceGateDecision.CONFIRM:
        _confirm(
            f"Run skill script {filename} in the workspace?",
            filename,
        )

    refusal = await _refusal_if_busy()
    if refusal is not None:
        return refusal
    client = await _ensure_client()
    rel = filename if filename.startswith("scripts/") else f"scripts/{filename.split('/')[-1]}"
    await client.put(rel, script.content, overwrite=True)
    timeout = 120
    if _settings is not None:
        timeout = int(getattr(_settings, "workspace_timeout_seconds", 120) or 120)
    return await _run_and_maybe_detach(
        command=f"skill-script {filename}",
        origin=WorkspaceRunOrigin(workspace_run_origin.get()),
        argv=["bash", "-lc", f"python3 {rel} || bash {rel}"],
        timeout_seconds=timeout,
        skill_id=skill.id,
        skill_script_path=filename,
    )


@tool(
    access=ToolAccess.WRITE,
    description=(
        "Opt-in: ingest a workspace file into Ze's memory. "
        "Does not delete the workspace file. Placing a file is not ingestion."
    ),
)
async def ingest_workspace_file(path: str) -> str:
    decision = await _decide(WorkspaceAction.INGEST)
    if decision is WorkspaceGateDecision.DENY:
        return "Ingesting a workspace file is not allowed."
    if decision is WorkspaceGateDecision.CONFIRM:
        _confirm(
            f"Ingest workspace file {path} into memory?",
            path,
        )
    if _ingestion is None:
        return "Ingestion pipeline is not available."
    client = await _ensure_client()
    data = await client.download(path)
    result = await _ingestion.ingest(
        SimpleNamespace(url=None, file_bytes=data, mime_type=None, label=path)
    )
    return (
        f"Ingested {path} ({getattr(result, 'facts_count', 0)} facts). "
        "The workspace file was not deleted."
    )


@tool(
    access=ToolAccess.WRITE,
    description=(
        "Empty the workspace after confirmation. Stops an in-progress run, "
        "then removes all files."
    ),
)
async def workspace_reset() -> str:
    decision = await _decide(WorkspaceAction.RESET)
    if decision is WorkspaceGateDecision.DENY:
        return "Resetting the workspace is not allowed."
    if decision is WorkspaceGateDecision.CONFIRM:
        _confirm(
            "Reset the workspace? All files will be removed.",
            "reset",
            editable=False,
        )
    client = await _ensure_client()
    await client.reset()
    if _store is not None:
        await _store.mark_reset()
    return "Workspace reset. All files were removed."
