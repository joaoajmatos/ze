"""REST tests for /api/v0/workspace (Phase 115, User Story 1)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.dependencies import require_api_key
from ze_api.api.routes.workspace import router
from ze_workspace.errors import (
    WorkspaceFullError,
    WorkspacePathError,
)
from ze_workspace.types import (
    WorkspaceFile,
    WorkspaceMode,
    WorkspaceRun,
    WorkspaceRunOrigin,
    WorkspaceRunStatus,
    WorkspaceState,
)

API_KEY = "test-key"


def _make_app(store=None, client=None, pipeline=None) -> FastAPI:
    app = FastAPI()
    store = store or AsyncMock()
    client = client or AsyncMock()
    pipeline = pipeline or AsyncMock()
    app.state.container = SimpleNamespace(
        workspace_store=store,
        workspace_client=client,
        ingestion_pipeline=pipeline,
    )
    app.dependency_overrides[require_api_key] = lambda: None
    app.include_router(router, prefix="/api/v0")
    return app


def _file(path="notes.txt", size=5) -> WorkspaceFile:
    return WorkspaceFile(
        path=path,
        size=size,
        modified_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
        is_dir=False,
    )


@pytest.mark.asyncio
async def test_get_status_and_mode():
    store = AsyncMock()
    store.get_state = AsyncMock(
        return_value=WorkspaceState(mode=WorkspaceMode.ASK)
    )
    store.get_mode = AsyncMock(return_value=WorkspaceMode.ASK)
    client = AsyncMock()
    client.health = AsyncMock(return_value=True)
    client.stat = AsyncMock(
        return_value=SimpleNamespace(
            bytes_used=12, bytes_ceiling=1073741824, busy=False
        )
    )
    app = _make_app(store=store, client=client)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        status = await http.get("/api/v0/workspace")
        mode = await http.get("/api/v0/workspace/mode")
    assert status.status_code == 200
    assert status.json()["mode"] == "ask"
    assert status.json()["available"] is True
    assert mode.json() == {"mode": "ask"}


@pytest.mark.asyncio
async def test_patch_mode_persists():
    store = AsyncMock()
    store.set_mode = AsyncMock(
        return_value=WorkspaceState(mode=WorkspaceMode.AUTO)
    )
    app = _make_app(store=store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        resp = await http.patch("/api/v0/workspace/mode", json={"mode": "auto"})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "auto"
    store.set_mode.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_and_get_file():
    client = AsyncMock()
    client.list_dir = AsyncMock(return_value=[_file()])
    client.download = AsyncMock(return_value=b"hello")
    app = _make_app(client=client)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        listing = await http.get("/api/v0/workspace/files")
        body = await http.get("/api/v0/workspace/files/notes.txt")
    assert listing.status_code == 200
    assert listing.json()["files"][0]["path"] == "notes.txt"
    assert body.status_code == 200
    assert body.content == b"hello"


@pytest.mark.asyncio
async def test_upload_dedupes_name():
    client = AsyncMock()
    client.list_dir = AsyncMock(return_value=[_file("notes.txt")])
    client.upload = AsyncMock(return_value={"path": "notes-1.txt", "size": 4})
    app = _make_app(client=client)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        resp = await http.post(
            "/api/v0/workspace/files",
            files={"file": ("notes.txt", b"data", "text/plain")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["path"] == "notes-1.txt"
    assert data["requested_path"] == "notes.txt"
    assert data["deduplicated"] is True


@pytest.mark.asyncio
async def test_upload_409_full():
    client = AsyncMock()
    client.list_dir = AsyncMock(return_value=[])
    client.upload = AsyncMock(side_effect=WorkspaceFullError("full"))
    app = _make_app(client=client)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        resp = await http.post(
            "/api/v0/workspace/files",
            files={"file": ("big.bin", b"x", "application/octet-stream")},
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_upload_400_escape():
    client = AsyncMock()
    client.list_dir = AsyncMock(return_value=[])
    client.upload = AsyncMock(side_effect=WorkspacePathError("outside_workspace"))
    app = _make_app(client=client)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        resp = await http.post(
            "/api/v0/workspace/files",
            data={"path": "../etc/passwd"},
            files={"file": ("x.txt", b"x", "text/plain")},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_runs():
    store = AsyncMock()
    store.list_runs = AsyncMock(
        return_value=[
            WorkspaceRun(
                id=uuid4(),
                command="echo hi",
                origin=WorkspaceRunOrigin.CONVERSATION,
                status=WorkspaceRunStatus.SUCCEEDED,
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                output_preview="hi",
            )
        ]
    )
    app = _make_app(store=store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        resp = await http.get("/api/v0/workspace/runs")
    assert resp.status_code == 200
    assert resp.json()["runs"][0]["command"] == "echo hi"


@pytest.mark.asyncio
async def test_ingest_calls_pipeline_with_file_bytes_and_keeps_file():
    client = AsyncMock()
    client.download = AsyncMock(return_value=b"csv-bytes")
    pipeline = SimpleNamespace(
        ingest=AsyncMock(
            return_value=SimpleNamespace(
                ingestion_id=uuid4(),
                content_type=SimpleNamespace(value="plain_text"),
                summary="ok",
                facts_count=1,
                tags=[],
            )
        )
    )
    app = _make_app(client=client, pipeline=pipeline)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        resp = await http.post("/api/v0/workspace/files/report.csv/ingest")
    assert resp.status_code == 200
    req = pipeline.ingest.await_args.args[0]
    assert req.file_bytes == b"csv-bytes"
    client.delete.assert_not_awaited()
    assert resp.json()["facts_count"] == 1
