from __future__ import annotations

from unittest.mock import AsyncMock

from ze_api.api.websocket.commands import handle_command
from ze_api.api.websocket.connection import ConnectionManager


def _make_ws():
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    ws.headers = {}
    return ws


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


async def test_cancel_with_two_pendings_only_drops_named_thread():
    mgr = ConnectionManager()
    ws = _make_ws()
    store = AsyncMock()
    store.list_unread = AsyncMock(return_value=[])
    await mgr.connect(ws, store)
    ws.send_json.reset_mock()

    container = AsyncMock()
    container.abort_invocation = AsyncMock()

    pending_configs = {
        "req-a": _config("thread-a"),
        "req-b": _config("thread-b"),
    }
    thread_pending_requests = {
        "thread-a": {"req-a"},
        "thread-b": {"req-b"},
    }

    await handle_command(
        ws,
        {"type": "command", "name": "cancel", "thread_id": "thread-a"},
        container,
        mgr,
        pending_configs,
        thread_pending_requests,
    )

    assert "req-a" not in pending_configs
    assert pending_configs["req-b"] == _config("thread-b")
    assert "thread-a" not in thread_pending_requests
    assert thread_pending_requests["thread-b"] == {"req-b"}
    container.abort_invocation.assert_awaited_once_with("thread-a")


async def test_cancel_without_thread_id_does_not_clear_pendings():
    mgr = ConnectionManager()
    ws = _make_ws()
    store = AsyncMock()
    store.list_unread = AsyncMock(return_value=[])
    await mgr.connect(ws, store)
    ws.send_json.reset_mock()

    container = AsyncMock()
    container.abort_invocation = AsyncMock()

    pending_configs = {
        "req-a": _config("thread-a"),
        "req-b": _config("thread-b"),
    }
    thread_pending_requests = {
        "thread-a": {"req-a"},
        "thread-b": {"req-b"},
    }

    await handle_command(
        ws,
        {"type": "command", "name": "cancel"},
        container,
        mgr,
        pending_configs,
        thread_pending_requests,
    )

    assert set(pending_configs) == {"req-a", "req-b"}
    container.abort_invocation.assert_not_awaited()
    frames = [call[0][0] for call in ws.send_json.call_args_list]
    assert any(f.get("type") == "error" for f in frames)
