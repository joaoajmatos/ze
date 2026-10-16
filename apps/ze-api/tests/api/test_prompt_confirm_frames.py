"""Every confirm_request producer emits the one frame contract (Phase 181, review H3).

Goal gates, goal suggestions, the workspace reset and the interface's
send_confirmation are prompt-only confirmations: kind "prompt", no items, the
producer's own actions. Each frame must validate against WsConfirmRequestFrame.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_agents.interface.types import Action, ConfirmationRequest, Notification
from ze_api.api.dependencies import require_api_key
from ze_api.api.routes.workspace import router as workspace_router
from ze_api.api.schemas import WsConfirmRequestFrame
from ze_api.api.websocket.frames import frame_from_pending
from ze_api.interface.native import NativeAppInterface


def _interface() -> tuple[NativeAppInterface, MagicMock]:
    conn = MagicMock()
    conn.push = AsyncMock()
    conn.send_frame = AsyncMock()
    conn.connected = True
    iface = NativeAppInterface(
        message_store=AsyncMock(), connection_manager=conn, notifier=AsyncMock()
    )
    return iface, conn


def _sent_confirm_frame(conn: MagicMock) -> dict:
    frames = [c.args[0] for c in conn.send_frame.call_args_list]
    (frame,) = [f for f in frames if f.get("type") == "confirm_request"]
    return frame


async def test_a_goal_gate_action_request_is_a_prompt_frame() -> None:
    iface, conn = _interface()

    await iface.push(
        Notification(
            content="<b>Goal</b> — proposed plan",
            format="html",
            urgency="high",
            actions=[
                Action(label="Start goal", payload="goal_plan:yes:abc"),
                Action(label="Cancel", payload="goal_plan:no:abc"),
            ],
        )
    )

    frame = _sent_confirm_frame(conn)
    WsConfirmRequestFrame.model_validate(frame)
    assert (frame["kind"], frame["round"], frame["items"]) == ("prompt", 1, [])
    assert frame["title"] == "Goal — proposed plan"
    assert [a["value"] for a in frame["actions"]] == [
        "goal_plan:yes:abc",
        "goal_plan:no:abc",
    ]
    assert "prompt" not in frame


async def test_send_confirmation_is_a_prompt_frame() -> None:
    iface, conn = _interface()

    await iface.send_confirmation(
        ConfirmationRequest(content="Delete 10 emails?", options=["Approve", "Cancel"])
    )

    frame = _sent_confirm_frame(conn)
    WsConfirmRequestFrame.model_validate(frame)
    assert (frame["kind"], frame["items"]) == ("prompt", [])
    assert frame["title"] == "Delete 10 emails?"


async def test_the_workspace_reset_frame_and_its_replay_are_prompt_frames() -> None:
    app = FastAPI()
    store = AsyncMock()
    conn_mgr = AsyncMock()
    app.state.container = SimpleNamespace(
        workspace_store=AsyncMock(),
        workspace_client=AsyncMock(),
        ingestion_pipeline=AsyncMock(),
        confirmation_store=store,
        connection_manager=conn_mgr,
    )
    app.dependency_overrides[require_api_key] = lambda: None
    app.include_router(workspace_router, prefix="/api/v0")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        resp = await http.post("/api/v0/workspace/reset")
    assert resp.status_code == 202

    live = conn_mgr.send_frame.await_args.args[0]
    WsConfirmRequestFrame.model_validate(live)
    assert (live["kind"], live["items"]) == ("prompt", [])
    assert [a["value"] for a in live["actions"]] == ["approve", "deny"]

    saved = store.save.await_args.kwargs
    replay = frame_from_pending(
        {
            "thread_id": saved["thread_id"],
            "request_id": saved["request_id"],
            "prompt": saved["prompt"],
            "actions": saved["actions"],
            "expires_at": saved["expires_at"],
        }
    )
    WsConfirmRequestFrame.model_validate(replay)
    assert replay["id"] == live["id"]
    assert (replay["kind"], replay["title"], replay["actions"]) == (
        "prompt",
        live["title"],
        live["actions"],
    )
