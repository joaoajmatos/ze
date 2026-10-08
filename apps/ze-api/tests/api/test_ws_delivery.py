from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_api.api.websocket.connection import ConnectionManager
from ze_api.interface.native import NativeAppInterface
from ze_core.conversation.messages import Message
from ze_core.conversation.messages.types import MessageTrace


def _make_ws() -> AsyncMock:
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    ws.headers = {}
    return ws


async def _connected(ws: AsyncMock) -> ConnectionManager:
    mgr = ConnectionManager()
    store = AsyncMock()
    store.list_unread = AsyncMock(return_value=[])
    await mgr.connect(ws, store)
    ws.send_json.reset_mock()
    return mgr


def _message() -> Message:
    return Message(
        id=uuid4(),
        role="assistant",
        text="hi",
        components=[],
        read=False,
        created_at=datetime.now(timezone.utc),
        thread_id="t1",
    )


async def test_send_frame_serialization_error_keeps_socket():
    ws = _make_ws()
    mgr = await _connected(ws)
    ws.send_json.side_effect = [TypeError("not JSON serializable"), None]

    await mgr.send_frame({"type": "trace_update", "bad": object()}, "t1")

    assert mgr.connected
    await mgr.send_frame({"type": "typing"}, "t1")
    assert ws.send_json.call_count == 2


async def test_push_serialization_error_keeps_socket():
    ws = _make_ws()
    mgr = await _connected(ws)
    ws.send_json.side_effect = [ValueError("Out of range float"), None]

    await mgr.push(_message(), "t1")

    assert mgr.connected
    await mgr.push(_message(), "t1")
    assert ws.send_json.call_count == 2


async def test_send_frame_transport_error_clears_socket():
    ws = _make_ws()
    mgr = await _connected(ws)
    ws.send_json.side_effect = RuntimeError("Cannot call send once closed")

    await mgr.send_frame({"type": "typing"}, "t1")

    assert not mgr.connected


async def test_push_transport_error_clears_socket():
    ws = _make_ws()
    mgr = await _connected(ws)
    ws.send_json.side_effect = RuntimeError("websocket.close already sent")

    await mgr.push(_message(), "t1")

    assert not mgr.connected


async def test_reply_delivered_after_failed_trace_update_frame():
    ws = _make_ws()
    mgr = await _connected(ws)

    def _send(frame):
        if frame["type"] == "trace_update":
            raise TypeError("not JSON serializable")

    ws.send_json.side_effect = _send
    store = AsyncMock()
    iface = NativeAppInterface(
        message_store=store, connection_manager=mgr, notifier=None
    )
    trace = MessageTrace(
        agent="research",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.1,
        is_compound=False,
        subtasks=[],
    )
    trace.agent = object()  # type: ignore[assignment]

    await iface.send_with_thread("the answer", thread_id="t1", trace=trace)

    assert mgr.connected
    types = [c.args[0]["type"] for c in ws.send_json.call_args_list]
    assert "message" in types
