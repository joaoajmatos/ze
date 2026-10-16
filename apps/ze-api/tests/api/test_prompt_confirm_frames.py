"""Every confirm_request producer emits the one frame contract (Phase 181, review H3).

Goal gates, goal suggestions and the interface's
send_confirmation are prompt-only confirmations: kind "prompt", no items, the
producer's own actions. Each frame must validate against WsConfirmRequestFrame.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


from ze_agents.interface.types import Action, ConfirmationRequest, Notification
from ze_api.api.schemas import WsConfirmRequestFrame
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
