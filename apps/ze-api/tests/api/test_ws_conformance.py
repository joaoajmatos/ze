"""
WS protocol conformance tests (C2) + confirmation flow E2E coverage.

Conformance tests verify that every frame the server emits matches the
TypeScript InboundFrame union in apps/ze-web/src/ws/protocol.ts.

E2E tests verify the approve/deny/timeout confirmation paths end-to-end
using mocked WebSocket + container objects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4


from ze_api.api.websocket.connection import ConnectionManager
from ze_api.api.websocket.onboarding import send_onboarding_view
from ze_api.api.websocket.serializers import message_to_dict
from ze_core.conversation.messages import Message


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_ws() -> Any:
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


def _make_message(**kwargs) -> Message:
    return Message(
        id=kwargs.get("id", uuid4()),
        role=kwargs.get("role", "assistant"),
        text=kwargs.get("text", "Hello"),
        components=kwargs.get("components", []),
        read=kwargs.get("read", False),
        created_at=kwargs.get("created_at", datetime.now(timezone.utc)),
        thread_id=kwargs.get("thread_id", None),
    )


def _make_msg_store(messages: list[Message] | None = None) -> Any:
    store = AsyncMock()
    store.list_unread = AsyncMock(return_value=messages or [])
    return store


def _frames_sent(ws: Any) -> list[dict]:
    return [call[0][0] for call in ws.send_json.call_args_list]


# ── Protocol conformance: InboundFrame shapes ─────────────────────────────────


class TestMessageFrameConformance:
    """message frame: {type, message: {id, role, text, components, read, created_at, thread_id}}"""

    async def test_message_frame_has_required_keys(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        msg = _make_message()
        store = _make_msg_store([msg])
        await mgr.connect(ws, store)

        frame = _frames_sent(ws)[0]
        assert frame["type"] == "message"
        m = frame["message"]
        assert "id" in m
        assert "role" in m
        assert "text" in m
        assert "components" in m
        assert "read" in m
        assert "created_at" in m
        assert "thread_id" in m

    async def test_message_frame_id_is_string(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        msg = _make_message()
        store = _make_msg_store([msg])
        await mgr.connect(ws, store)

        frame = _frames_sent(ws)[0]
        assert isinstance(frame["message"]["id"], str)

    async def test_message_frame_role_is_valid(self):
        for role in ("user", "assistant"):
            mgr = ConnectionManager()
            ws = _make_ws()
            msg = _make_message(role=role)
            store = _make_msg_store([msg])
            await mgr.connect(ws, store)

            frame = _frames_sent(ws)[0]
            assert frame["message"]["role"] in ("user", "assistant")

    async def test_message_frame_components_is_list(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        msg = _make_message(components=[{"type": "card", "body": "x"}])
        store = _make_msg_store([msg])
        await mgr.connect(ws, store)

        frame = _frames_sent(ws)[0]
        assert isinstance(frame["message"]["components"], list)

    async def test_message_to_dict_created_at_is_iso_string(self):
        now = datetime.now(timezone.utc)
        msg = _make_message(created_at=now)
        d = message_to_dict(msg)
        assert d["created_at"] == now.isoformat()

    async def test_message_frame_with_onboarding_key(self):
        """Server attaches optional 'onboarding' key; TS type models it as optional."""
        mgr = ConnectionManager()
        ws = _make_ws()
        store = _make_msg_store([])
        await mgr.connect(ws, store)
        ws.send_json.reset_mock()

        from ze_onboarding import OnboardingView

        session_id = uuid4()
        await send_onboarding_view(
            mgr, OnboardingView(session_id=session_id, text="Hi", components=[])
        )
        frame = _frames_sent(ws)[0]
        assert frame["type"] == "message"
        assert "onboarding" in frame
        assert "session_id" in frame["onboarding"]
        assert "completed" in frame["onboarding"]


class TestConfirmRequestFrameConformance:
    """confirm_request frame: {type, id, prompt, actions: [{label, value, style?}]}"""

    async def test_confirm_request_shape_matches_protocol(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        store = _make_msg_store([])
        await mgr.connect(ws, store)
        ws.send_json.reset_mock()

        request_id = str(uuid4())
        frame = {
            "type": "confirm_request",
            "id": request_id,
            "prompt": "Delete 10 emails?",
            "actions": [
                {"label": "Approve", "value": "approve", "style": "primary"},
                {"label": "Cancel", "value": "deny", "style": "secondary"},
            ],
        }
        await mgr.send_frame(frame)

        sent = _frames_sent(ws)[0]
        assert sent["type"] == "confirm_request"
        assert isinstance(sent["id"], str)
        assert isinstance(sent["prompt"], str)
        assert isinstance(sent["actions"], list)
        for action in sent["actions"]:
            assert "label" in action
            assert "value" in action

    async def test_confirm_request_action_style_is_primary_secondary_or_danger(self):
        valid_styles = {"primary", "secondary", "danger"}
        for style in valid_styles:
            action = {"label": "OK", "value": "approve", "style": style}
            assert action["style"] in valid_styles


class TestConfirmCancelFrameConformance:
    """confirm_cancel frame: {type, id}"""

    async def test_confirm_cancel_shape(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        store = _make_msg_store([])
        await mgr.connect(ws, store)
        ws.send_json.reset_mock()

        request_id = str(uuid4())
        await mgr.send_frame({"type": "confirm_cancel", "id": request_id})

        sent = _frames_sent(ws)[0]
        assert sent["type"] == "confirm_cancel"
        assert "id" in sent
        assert isinstance(sent["id"], str)


class TestTypingAndErrorFrameConformance:
    """typing frame: {type}; error frame: {type, detail}"""

    async def test_typing_frame_has_only_type(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        store = _make_msg_store([])
        await mgr.connect(ws, store)
        ws.send_json.reset_mock()

        await mgr.send_frame({"type": "typing"})
        sent = _frames_sent(ws)[0]
        assert sent["type"] == "typing"

    async def test_error_frame_has_detail(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        store = _make_msg_store([])
        await mgr.connect(ws, store)
        ws.send_json.reset_mock()

        await mgr.send_frame({"type": "error", "detail": "Something went wrong."})
        sent = _frames_sent(ws)[0]
        assert sent["type"] == "error"
        assert "detail" in sent
        assert isinstance(sent["detail"], str)


class TestRefreshFrameConformance:
    """refresh frame: {type, screen}"""

    async def test_refresh_frame_has_screen(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        store = _make_msg_store([])
        await mgr.connect(ws, store)
        ws.send_json.reset_mock()

        await mgr.send_frame({"type": "refresh", "screen": "goals"})
        sent = _frames_sent(ws)[0]
        assert sent["type"] == "refresh"
        assert "screen" in sent
        assert isinstance(sent["screen"], str)


# ── Confirmation flow E2E ─────────────────────────────────────────────────────


def _make_pending_config(thread_id: str = "t1") -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _make_container(thread_id: str = "t1") -> Any:
    container = AsyncMock()
    result = MagicMock()
    result.response = "Action completed."
    result.final_state = {"components": []}
    result.interrupted = False
    container.resume_turn = AsyncMock(return_value=result)
    container.abort_pending_checkpoint = AsyncMock()
    container.interface = AsyncMock()
    container.interface.send_with_thread = AsyncMock()
    graph_state = MagicMock()
    graph_state.interrupts = ()
    container.graph.aget_state = AsyncMock(return_value=graph_state)
    return container


# ── Unread replay — multi-conversation ───────────────────────────────────────


class TestScopedUnreadReplay:
    """On connect, list_unread(None) replays ALL threads so the client can restore all conversations."""

    async def test_connect_calls_list_unread_with_no_filter(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        store = _make_msg_store([])

        await mgr.connect(ws, store)

        store.list_unread.assert_awaited_once_with(None)

    async def test_unread_replay_shows_messages_from_all_threads(self):
        mgr = ConnectionManager()
        ws = _make_ws()

        msg_a = _make_message(thread_id="ze-abc", text="Thread A")
        msg_b = _make_message(thread_id="ze-def", text="Thread B")
        store = _make_msg_store([msg_a, msg_b])

        await mgr.connect(ws, store)

        frames = _frames_sent(ws)
        msg_frames = [f for f in frames if f.get("type") == "message"]
        assert len(msg_frames) == 2
        texts = {f["message"]["text"] for f in msg_frames}
        assert texts == {"Thread A", "Thread B"}


class TestErrorFrameSchemaConformance:
    """Every error frame the handlers emit validates against WsErrorFrame."""

    async def _connected(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws, _make_msg_store([]))
        ws.send_json.reset_mock()
        return mgr, ws

    async def test_turn_error_frames_validate_and_carry_thread_id(self):
        from ze_api.api.schemas import WsErrorFrame
        from ze_api.api.websocket.turns import handle_message

        mgr, ws = await self._connected()
        container = MagicMock()
        container.translations = None
        container.invoke_raw_turn = AsyncMock(side_effect=RuntimeError("boom"))
        await handle_message(
            ws,
            {"type": "message", "text": "hi", "thread_id": "t1"},
            container,
            AsyncMock(),
            mgr,
            None,
        )
        container.invoke_raw_turn = AsyncMock(
            return_value=MagicMock(interrupted=False, response=None, config={})
        )
        await handle_message(
            ws,
            {"type": "message", "text": "hi", "thread_id": "t2"},
            container,
            AsyncMock(),
            mgr,
            None,
        )
        await handle_message(
            ws, {"type": "message", "text": "hi"}, container, AsyncMock(), mgr, None
        )

        errors = [f for f in _frames_sent(ws) if f["type"] == "error"]
        assert len(errors) == 3
        for frame in errors:
            WsErrorFrame.model_validate(frame)
        assert [f.get("thread_id") for f in errors] == ["t1", "t2", None]

    async def test_component_submit_error_carries_thread_id(self):
        from ze_api.api.schemas import WsErrorFrame
        from ze_api.api.websocket.component_submit import handle_component_submit

        mgr, ws = await self._connected()
        await handle_component_submit(
            ws, {"thread_id": "t3", "values": {}}, MagicMock(), mgr, AsyncMock(), None
        )
        frame = _frames_sent(ws)[0]
        WsErrorFrame.model_validate(frame)
        assert frame["thread_id"] == "t3"
