from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from ze_workspace.client import WorkspaceClient
from ze_workspace.errors import (
    WorkspaceBusyError,
    WorkspaceFullError,
    WorkspaceNotFoundError,
    WorkspacePathError,
    WorkspaceRunAlreadyTerminalError,
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


async def test_start_run_returns_immediately_on_200():
    client = make_client()
    client._client = AsyncMock()
    client._client.request = AsyncMock(
        return_value=make_httpx_response(200, {"id": "abc"})
    )
    await client.start_run(["echo", "hi"], uuid4())
    body = client._client.request.await_args.kwargs["json"]
    assert body["command"] == ["echo", "hi"]
    assert "id" in body


async def test_start_run_409_busy_names_running_run():
    client = make_client()
    client._client = AsyncMock()
    client._client.request = AsyncMock(
        return_value=make_httpx_response(
            409, {"error": "busy", "id": "r1", "command": ["sleep", "5"]}
        )
    )
    with pytest.raises(WorkspaceBusyError, match="r1"):
        await client.start_run(["echo", "hi"], uuid4())


async def test_get_run_returns_status():
    client = make_client()
    client._client = AsyncMock()
    run_id = uuid4()
    client._client.request = AsyncMock(
        return_value=make_httpx_response(
            200,
            {
                "id": str(run_id),
                "status": "running",
                "exit_code": None,
                "timed_out": False,
                "stdout_preview": "hi",
                "stderr_preview": "",
                "output_file_path": None,
                "files_touched": [],
            },
        )
    )
    status = await client.get_run(run_id)
    assert status is not None
    assert status.status == "running"
    assert status.stdout_preview == "hi"


async def test_get_run_returns_none_on_404():
    client = make_client()
    client._client = AsyncMock()
    client._client.request = AsyncMock(
        return_value=make_httpx_response(404, {"error": "not_found"})
    )
    assert await client.get_run(uuid4()) is None


async def test_get_run_redacts_preview():
    client = make_client()
    client._client = AsyncMock()
    client._client.request = AsyncMock(
        return_value=make_httpx_response(
            200,
            {
                "status": "succeeded",
                "exit_code": 0,
                "timed_out": False,
                "stdout_preview": "OPENROUTER_API_KEY=sk-secret",
                "stderr_preview": "",
                "output_file_path": None,
                "files_touched": [],
            },
        )
    )
    status = await client.get_run(uuid4())
    assert "sk-secret" not in status.stdout_preview
    assert "[redacted]" in status.stdout_preview


async def test_cancel_run_success():
    client = make_client()
    client._client = AsyncMock()
    client._client.request = AsyncMock(
        return_value=make_httpx_response(200, {"ok": True})
    )
    await client.cancel_run(uuid4())  # does not raise


async def test_cancel_run_404_not_found():
    client = make_client()
    client._client = AsyncMock()
    client._client.request = AsyncMock(
        return_value=make_httpx_response(404, {"error": "not_found"})
    )
    with pytest.raises(WorkspaceNotFoundError):
        await client.cancel_run(uuid4())


async def test_cancel_run_409_already_terminal():
    client = make_client()
    client._client = AsyncMock()
    client._client.request = AsyncMock(
        return_value=make_httpx_response(
            409, {"error": "already_terminal", "status": "succeeded"}
        )
    )
    with pytest.raises(WorkspaceRunAlreadyTerminalError):
        await client.cancel_run(uuid4())


async def test_watch_run_yields_events_then_stops_at_exit():
    import json

    client = make_client()
    lines = [
        json.dumps({"seq": 0, "type": "stdout", "data": "hi\n"}),
        json.dumps({"seq": 1, "type": "exit", "data": "", "exit_code": 0, "timed_out": False}),
    ]

    class FakeStreamResponse:
        status_code = 200

        async def aread(self):
            return b""

        async def aiter_lines(self):
            for line in lines:
                yield line

    class FakeStreamCtx:
        async def __aenter__(self):
            return FakeStreamResponse()

        async def __aexit__(self, *a):
            return False

    client._client = MagicMock()
    client._client.stream = MagicMock(return_value=FakeStreamCtx())

    events = [ev async for ev in client.watch_run(uuid4())]
    assert [e.type for e in events] == ["stdout", "exit"]
    assert events[-1].exit_code == 0


async def test_watch_run_404_raises_not_found():
    client = make_client()

    class FakeStreamResponse:
        status_code = 404

        async def aread(self):
            return b'{"error": "not_found"}'

    class FakeStreamCtx:
        async def __aenter__(self):
            return FakeStreamResponse()

        async def __aexit__(self, *a):
            return False

    client._client = MagicMock()
    client._client.stream = MagicMock(return_value=FakeStreamCtx())

    with pytest.raises(WorkspaceNotFoundError):
        async for _ in client.watch_run(uuid4()):
            pass


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
