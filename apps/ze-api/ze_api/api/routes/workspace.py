from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

from ze_api.api.dependencies import (
    get_ingestion_pipeline,
    get_workspace_client,
    get_workspace_store,
    require_api_key,
)
from ze_api.api.schemas import (
    WorkspaceFileListResponse,
    WorkspaceIngestResponse,
    WorkspaceModeResponse,
    WorkspaceModeUpdate,
    WorkspaceRunListResponse,
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
    description="Live sidecar health plus persisted mode and last-used timestamps.",
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
    "/mode",
    response_model=WorkspaceModeResponse,
    operation_id="getWorkspaceMode",
    summary="Get workspace mode",
    description="Return the persisted workspace mode (Off / Plan / Ask / Auto-edit / Auto).",
)
async def get_workspace_mode(
    store: WorkspaceStore = Depends(get_workspace_store),
) -> WorkspaceModeResponse:
    data = await workspace_rest.get_mode(store)
    return WorkspaceModeResponse.model_validate(data)


@router.patch(
    "/mode",
    response_model=WorkspaceModeResponse,
    operation_id="updateWorkspaceMode",
    summary="Set workspace mode",
    description="Persist the workspace mode until the user changes it again. Does not confirm.",
)
async def update_workspace_mode(
    body: WorkspaceModeUpdate,
    store: WorkspaceStore = Depends(get_workspace_store),
) -> WorkspaceModeResponse:
    try:
        data = await workspace_rest.set_mode(store, body.mode)
    except WorkspaceError as exc:
        _raise_workspace(exc)
    return WorkspaceModeResponse.model_validate(data)


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


@router.post(
    "/files/{file_path:path}/ingest",
    response_model=WorkspaceIngestResponse,
    operation_id="ingestWorkspaceFile",
    summary="Ingest a workspace file into memory",
    description="Opt-in ingest of an existing workspace file. The file is not deleted.",
)
async def ingest_workspace_file(
    file_path: str,
    client: WorkspaceClient = Depends(get_workspace_client),
    pipeline: object = Depends(get_ingestion_pipeline),
) -> WorkspaceIngestResponse:
    try:
        data = await workspace_rest.ingest_file(client, pipeline, file_path)
    except (
        WorkspaceUnavailableError,
        WorkspaceBusyError,
        WorkspacePathError,
        WorkspaceNotFoundError,
        WorkspaceFullError,
    ) as exc:
        _raise_workspace(exc)
    return WorkspaceIngestResponse.model_validate(data)


@router.get(
    "/files/{file_path:path}",
    operation_id="getWorkspaceFile",
    summary="Download a workspace file",
    description="Return file bytes as an attachment. Directories and escapes are 400.",
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
