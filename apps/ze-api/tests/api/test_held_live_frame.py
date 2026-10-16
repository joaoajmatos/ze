"""A hold that opens while the app is open shows its card at once (Phase 181, Tally UI c).

The live push sends the same confirm_request (kind "held") that the on-connect
replay sends, and no chat bubble.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from ze_agents.interface.types import Notification
from ze_api.api.schemas import WsConfirmRequestFrame
from ze_api.api.ws.held import held_frame, held_push_frame
from ze_api.interface.native import NativeAppInterface
from ze_automation.holds.types import HeldWrite, HeldWriteStatus
from ze_automation.push_kinds import WRITE_APPROVAL_HELD


def _hold(status: HeldWriteStatus = HeldWriteStatus.OPEN) -> HeldWrite:
    return HeldWrite(
        request_id="r1",
        source="workflow",
        owner_ref="exec-1",
        items=[
            {
                "item_id": "i1",
                "agent": "messenger",
                "tool": "send_email",
                "effect_phrase": "send an email",
                "summary": "to: ivy@example.com",
            }
        ],
        payload={"source_name": "Weekly goals summary"},
        status=status,
    )


def _store(hold: HeldWrite | None) -> AsyncMock:
    store = AsyncMock()
    store.get = AsyncMock(return_value=hold)
    return store


def _held_push() -> Notification:
    return Notification(
        content="send an email: to: ivy@example.com",
        id="n-1",
        event_type="write_approval_held",
        title="Workflow 'Weekly goals summary' needs your OK",
        target_type="held_write",
        target_id="r1",
        in_chat=False,
    )


def test_a_held_write_push_is_not_a_chat_message() -> None:
    assert WRITE_APPROVAL_HELD.in_chat is False


async def test_the_live_hold_push_sends_the_replay_card_and_no_bubble() -> None:
    conn = MagicMock()
    conn.connected = True
    conn.send_frame = AsyncMock()
    conn.push = AsyncMock()
    store = AsyncMock()
    hold = _hold()
    iface = NativeAppInterface(
        message_store=store,
        connection_manager=conn,
        notifier=AsyncMock(),
        confirm_frame_for=held_push_frame(_store(hold)),
    )

    await iface.push(_held_push())

    frames = [c.args[0] for c in conn.send_frame.call_args_list]
    card = next(f for f in frames if f["type"] == "confirm_request")
    assert card == held_frame(hold)
    WsConfirmRequestFrame.model_validate(card)
    assert [f["type"] for f in frames].count("notification") == 1
    store.save.assert_not_called()
    conn.push.assert_not_called()


async def test_no_card_for_a_hold_that_is_no_longer_open() -> None:
    frame_for = held_push_frame(_store(_hold(HeldWriteStatus.APPROVED)))

    assert await frame_for(_held_push()) is None


async def test_no_card_for_a_push_that_is_not_a_hold() -> None:
    frame_for = held_push_frame(_store(_hold()))
    push = Notification(
        content="x", event_type="other", target_type="goal", target_id="g"
    )

    assert await frame_for(push) is None
