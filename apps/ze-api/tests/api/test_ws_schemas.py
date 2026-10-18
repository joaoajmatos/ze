from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from ze_api.api.ws.connection import ConnectionManager
from ze_api.api.ws.schemas import WsInboundFrame, WsOutboundFrame
from ze_core.conversation.messages import Message

_ui_action = {
    "type": "ui_action",
    "id": "6c1",
    "thread_id": "t-1",
    "action": {
        "kind": "tool",
        "owner": "news",
        "tool": "mark_source_read",
        "args": {"source_id": "s-12"},
    },
}


def test_ui_action_frame_round_trips():
    frame = TypeAdapter(WsOutboundFrame).validate_python(_ui_action)
    assert frame.model_dump(exclude_none=True) == _ui_action


@pytest.mark.parametrize(
    "action",
    [
        {"kind": "ask", "text": "hi"},
        {"kind": "navigate", "route": "/ask"},
        {"kind": "tool", "owner": "o", "tool": "t", "args": {}, "extra": 1},
        {"kind": "tool", "owner": "o", "tool": "t", "args": {"a": [1]}},
    ],
)
def test_ui_action_frame_carries_tool_actions_only(action):
    with pytest.raises(ValidationError):
        TypeAdapter(WsOutboundFrame).validate_python({**_ui_action, "action": action})


def test_ui_action_result_frame_round_trips():
    frame = {
        "type": "ui_action_result",
        "id": "6c1",
        "thread_id": "t-1",
        "ok": True,
        "line": "Marked as read.",
    }
    parsed = TypeAdapter(WsInboundFrame).validate_python(frame)
    assert parsed.model_dump(exclude_none=True) == frame
    busy = TypeAdapter(WsInboundFrame).validate_python(
        {**frame, "ok": False, "line": "Busy.", "code": "busy"}
    )
    assert busy.code == "busy"


def test_message_frame_carries_ui_version():
    frame = {
        "type": "message",
        "ui_version": "2.0",
        "message": {
            "id": str(uuid4()),
            "role": "assistant",
            "text": "hi",
            "components": [],
            "read": False,
            "thread_id": "t",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    assert TypeAdapter(WsInboundFrame).validate_python(frame).ui_version == "2.0"
    del frame["ui_version"]
    assert TypeAdapter(WsInboundFrame).validate_python(frame).ui_version is None


def _message(components: list[dict]) -> Message:
    return Message(
        id=uuid4(),
        role="assistant",
        text="x",
        components=components,
        read=False,
        created_at=datetime.now(timezone.utc),
        thread_id="t",
    )


async def test_live_push_stamps_ui_version_only_when_it_carries_components():
    ws = AsyncMock()
    manager = ConnectionManager()
    manager._ws = ws
    await manager.push(_message([{"type": "text", "content": "a"}]))
    await manager.push(_message([]))
    with_components, without = (c.args[0] for c in ws.send_json.call_args_list)
    assert with_components["ui_version"] == "2.0"
    assert "ui_version" not in without


def test_plugin_page_responses_carry_ui_version():
    from ze_news.api.schemas import PluginPageResponse as News
    from ze_personal.api.schemas import PluginPageResponse as Personal

    for cls in (News, Personal):
        assert cls(title="t", tree=[]).ui_version == "2.0"
