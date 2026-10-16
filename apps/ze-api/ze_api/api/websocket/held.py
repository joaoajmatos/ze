"""Held writes over the chat socket (Phase 181, FR-025): replay on connect, answer in chat."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from ze_agents.interface.types import Notification

from ze_api.api.websocket.connection import ConnectionManager
from ze_api.api.websocket.frames import build_confirm_frame
from ze_automation.holds.resumer import (
    HELD_TARGET_TYPE,
    HeldWriteEditError,
    HeldWriteNotFoundError,
    HeldWriteNotOpenError,
)
from ze_automation.holds.types import HeldWrite, HeldWriteStatus
from ze_logging import get_logger

log = get_logger(__name__)


def held_frame(hold: HeldWrite) -> dict[str, Any]:
    """The `confirm_request` frame (kind "held") for an open held write."""
    return build_confirm_frame(
        request_id=hold.request_id,
        thread_id=None,
        kind="held",
        round_=int(hold.payload.get("round") or 1),
        items=list(hold.items),
        expires_at=hold.expires_at,
        source={"kind": hold.source, "name": hold.payload.get("source_name", "")},
    )


def held_push_frame(
    held_store: Any,
) -> Callable[[Notification], Awaitable[dict[str, Any] | None]]:
    """The card a live hold push carries: the replay frame of that hold, if still open."""

    async def _frame(notification: Notification) -> dict[str, Any] | None:
        if notification.target_type != HELD_TARGET_TYPE or not notification.target_id:
            return None
        hold = await held_store.get(notification.target_id)
        if not isinstance(hold, HeldWrite) or hold.status != HeldWriteStatus.OPEN:
            return None
        return held_frame(hold)

    return _frame


async def open_held_frames(held_store: Any) -> list[dict[str, Any]]:
    holds = await held_store.list(HeldWriteStatus.OPEN)
    return [held_frame(h) for h in holds]


async def handle_held_confirm(
    data: dict, container: Any, conn_mgr: ConnectionManager, thread_id: str
) -> bool:
    """Answer a held write from chat. False when `data["id"]` is not a held write."""
    request_id = data.get("id", "")
    store = getattr(container, "held_write_store", None)
    resumer = getattr(container, "held_write_resumer", None)
    if store is None or resumer is None or not request_id:
        return False
    if not isinstance(await store.get(request_id), HeldWrite):
        return False
    choice = data.get("choice", "")
    if choice not in ("approve", "deny"):
        await conn_mgr.send_frame(
            {"type": "error", "detail": "invalid choice"}, thread_id
        )
        return True
    edits = data.get("edits") or {}
    try:
        hold = await resumer.decide(request_id, choice, edits)
    except (HeldWriteNotFoundError, HeldWriteNotOpenError):
        await conn_mgr.send_frame(
            {"type": "error", "detail": "No pending confirmation."}, thread_id
        )
        return True
    except HeldWriteEditError:
        await conn_mgr.send_frame(
            {"type": "error", "detail": "invalid edit"}, thread_id
        )
        return True
    log.info("held_write_answered", request_id=request_id, choice=choice, via="ws")
    resumer.resume_in_background(hold, choice, edits)
    await conn_mgr.send_frame({"type": "confirm_cancel", "id": request_id}, thread_id)
    return True
