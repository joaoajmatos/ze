from __future__ import annotations

import json
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import Response, StreamingResponse

from ze_api.api.deps import (
    get_workspace_client,
    get_workspace_run_watcher,
    get_workspace_store,
    require_api_key,
)
from ze_api.api.v0.workspace.schemas import (
    WorkspaceFileListResponse,
    WorkspaceRunListResponse,
    WorkspaceRunResponse,
    WorkspaceStatusResponse,
    WorkspaceUploadResponse,
)
from ze_workspace import rest as workspace_rest
from ze_workspace.client import WorkspaceClient
from ze_workspace.errors import (
    WorkspaceBusyError,
    WorkspaceError,
    WorkspaceFullError,
    WorkspaceNotFoundError,
    WorkspacePathError,
    WorkspaceUnavailableError,
)
from ze_workspace.followthrough import RunWatcher
from ze_workspace.sanitize import redact
from ze_workspace.store import WorkspaceStore

router = APIRouter(
    prefix="/workspace",
    tags=["workspace"],
    dependencies=[Depends(require_api_key)],
)


def _raise_workspace(exc: Exception) -> None:
    status = workspace_rest.http_status_for(exc)
    detail = str(exc) or type(exc).__name__
    raise HTTPException(status_code=status, detail=detail) from exc


@router.get(
    "",
    response_model=WorkspaceStatusResponse,
    operation_id="getWorkspace",
    summary="Get workspace status",
    description="Live sidecar health plus occupancy and last-used timestamps.",
)
async def get_workspace(
    store: WorkspaceStore = Depends(get_workspace_store),
    client: WorkspaceClient = Depends(get_workspace_client),
) -> WorkspaceStatusResponse:
    try:
        data = await workspace_rest.get_status(store, client)
    except WorkspaceError as exc:
        _raise_workspace(exc)
    return WorkspaceStatusResponse.model_validate(data)


@router.get(
    "/files",
    response_model=WorkspaceFileListResponse,
    operation_id="listWorkspaceFiles",
    summary="List workspace files",
    description="List files under a workspace-relative path (default: root). Origin is user REST.",
)
async def list_workspace_files(
    path: str = Query(default=""),
    client: WorkspaceClient = Depends(get_workspace_client),
) -> WorkspaceFileListResponse:
    try:
        data = await workspace_rest.list_files(client, path)
    except (
        WorkspaceUnavailableError,
        WorkspaceBusyError,
        WorkspacePathError,
        WorkspaceNotFoundError,
        WorkspaceFullError,
    ) as exc:
        _raise_workspace(exc)
    return WorkspaceFileListResponse.model_validate(data)


@router.post(
    "/files",
    response_model=WorkspaceUploadResponse,
    operation_id="uploadWorkspaceFile",
    summary="Place a file in the workspace",
    description=(
        "Upload bytes into the workspace without ingesting them. Duplicate names "
        "are stored under a distinct suffix rather than overwritten."
    ),
)
async def upload_workspace_file(
    file: UploadFile = File(...),
    path: str | None = Form(default=None),
    client: WorkspaceClient = Depends(get_workspace_client),
) -> WorkspaceUploadResponse:
    content = await file.read()
    filename = file.filename or "upload"
    try:
        data = await workspace_rest.upload_file(client, filename, content, dest=path)
    except (
        WorkspaceUnavailableError,
        WorkspaceBusyError,
        WorkspacePathError,
        WorkspaceNotFoundError,
        WorkspaceFullError,
    ) as exc:
        _raise_workspace(exc)
    return WorkspaceUploadResponse.model_validate(data)


@router.get(
    "/files/{file_path:path}",
    operation_id="getWorkspaceFile",
    summary="Download a workspace file",
    description="Return file bytes as an attachment. Directories and escapes are 400.",
    response_class=Response,
    responses={
        200: {
            "description": "File bytes",
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
        }
    },
)
async def get_workspace_file(
    file_path: str,
    client: WorkspaceClient = Depends(get_workspace_client),
) -> Response:
    try:
        data = await workspace_rest.download_file(client, file_path)
    except (
        WorkspaceUnavailableError,
        WorkspaceBusyError,
        WorkspacePathError,
        WorkspaceNotFoundError,
        WorkspaceFullError,
    ) as exc:
        _raise_workspace(exc)
    filename = file_path.rsplit("/", 1)[-1] or "file"
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete(
    "/files/{file_path:path}",
    status_code=204,
    operation_id="deleteWorkspaceFile",
    summary="Delete a workspace file",
    description="User-initiated delete. No confirmation. 404 if missing.",
)
async def delete_workspace_file(
    file_path: str,
    client: WorkspaceClient = Depends(get_workspace_client),
) -> Response:
    try:
        await workspace_rest.delete_file(client, file_path)
    except (
        WorkspaceUnavailableError,
        WorkspaceBusyError,
        WorkspacePathError,
        WorkspaceNotFoundError,
        WorkspaceFullError,
    ) as exc:
        _raise_workspace(exc)
    return Response(status_code=204)


@router.get(
    "/runs",
    response_model=WorkspaceRunListResponse,
    operation_id="listWorkspaceRuns",
    summary="List recent workspace runs",
    description="Persisted command history, optionally filtered by origin.",
)
async def list_workspace_runs(
    limit: int = Query(default=50, ge=1, le=200),
    origin: str | None = Query(default=None),
    store: WorkspaceStore = Depends(get_workspace_store),
) -> WorkspaceRunListResponse:
    try:
        data = await workspace_rest.list_runs(store, limit=limit, origin=origin)
    except (WorkspaceError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return WorkspaceRunListResponse.model_validate(data)


@router.get(
    "/runs/{run_id}/events",
    operation_id="watchWorkspaceRunEvents",
    summary="Watch a workspace run's live output",
    description=(
        "Streams already-produced output then live output as it happens "
        "(newline-delimited JSON), closing after the exit event (FR-005). "
        "Does not replace follow-through — the follow-up turn still fires "
        "exactly once when the run becomes terminal (FR-011)."
    ),
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Newline-delimited JSON events",
            "content": {
                "application/x-ndjson": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
        }
    },
)
async def watch_workspace_run_events(
    run_id: UUID,
    client: WorkspaceClient = Depends(get_workspace_client),
) -> StreamingResponse:
    status = await client.get_run(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"workspace run {run_id} not found")

    async def _proxy():
        async for event in client.watch_run(run_id):
            data = event.data
            if event.type in ("stdout", "stderr"):
                data = redact(data)
            line: dict = {"seq": event.seq, "type": event.type, "data": data}
            if event.type == "exit":
                line["exit_code"] = event.exit_code
                line["timed_out"] = event.timed_out
            yield (json.dumps(line) + "\n").encode("utf-8")

    return StreamingResponse(_proxy(), media_type="application/x-ndjson")


@router.post(
    "/runs/{run_id}/cancel",
    response_model=WorkspaceRunResponse,
    operation_id="cancelWorkspaceRun",
    summary="Cancel a workspace run",
    description=(
        "Stops an in-progress run. No confirmation is required (FR-009 — this "
        "is not workspace reset). 409 if the run already finished, 404 if the "
        "run id is unknown."
    ),
)
async def cancel_workspace_run(
    run_id: UUID,
    store: WorkspaceStore = Depends(get_workspace_store),
    client: WorkspaceClient = Depends(get_workspace_client),
    run_watcher: RunWatcher = Depends(get_workspace_run_watcher),
) -> WorkspaceRunResponse:
    try:
        data = await workspace_rest.cancel_run(store, client, run_watcher, run_id)
    except WorkspaceError as exc:
        _raise_workspace(exc)
    return WorkspaceRunResponse.model_validate(data)
