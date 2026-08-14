from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ze_workspace.client import WorkspaceClient
from ze_workspace.errors import (
    WorkspaceBusyError,
    WorkspaceFullError,
    WorkspacePathError,
    WorkspaceUnavailableError,
)


def make_client() -> WorkspaceClient:
    with patch("ze_workspace.client.httpx.AsyncClient"):
        return WorkspaceClient(
            base_url="http://workspace:8080", token="secret-token", timeout=30
        )


def make_httpx_response(
    status_code: int = 200, json_data: dict | None = None, text: str = ""
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    resp.content = text.encode() if text else b""
    resp.headers = {}
    return resp


async def test_health_false_on_connect_error():
    client = make_client()
    client._client = AsyncMock()
    client._client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
    assert await client.health() is False


async def test_health_true_on_ok():
    client = make_client()
    client._client = AsyncMock()
    client._client.get = AsyncMock(
        return_value=make_httpx_response(200, {"ok": True})
    )
    assert await client.health() is True


async def test_stat_unavailable_on_timeout():
    client = make_client()
    client._client = AsyncMock()
    client._client.request = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    with pytest.raises(WorkspaceUnavailableError, match="timed out"):
        await client.stat()


async def test_run_409_busy():
    client = make_client()
    client._client = AsyncMock()
    client._client.request = AsyncMock(
        return_value=make_httpx_response(409, {"error": "busy"})
    )
    with pytest.raises(WorkspaceBusyError):
        await client.run(["echo", "hi"])


async def test_put_413_full():
    client = make_client()
    client._client = AsyncMock()
    client._client.request = AsyncMock(
        return_value=make_httpx_response(413, {"error": "full"})
    )
    with pytest.raises(WorkspaceFullError):
        await client.put("a.txt", b"hello")


async def test_list_400_outside_workspace():
    client = make_client()
    client._client = AsyncMock()
    client._client.request = AsyncMock(
        return_value=make_httpx_response(400, {"error": "outside_workspace"})
    )
    with pytest.raises(WorkspacePathError, match="outside_workspace"):
        await client.list_dir("../")
