"""Held writes on the chat socket: replay on connect and answering in chat (Phase 181)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from ze_api.api.ws.connection import ConnectionManager
from ze_api.api.ws.held import handle_held_confirm, held_frame
from ze_automation.holds.resumer import HeldWriteResumer
from ze_automation.holds.types import HeldWrite, HeldWriteStatus
from tests.api.test_held_writes_routes import MemoryStore, _hold


def _setup(*holds: HeldWrite):
    store = MemoryStore(*holds)
    run = AsyncMock()
    resumer = HeldWriteResumer(store, resume_workflow=run)  # type: ignore[arg-type]
    container = SimpleNamespace(held_write_store=store, held_write_resumer=resumer)
    conn = SimpleNamespace(send_frame=AsyncMock())
    return container, conn, store, run


def test_held_frame_follows_the_confirm_request_contract() -> None:
    hold = _hold("r1", expires_at=datetime.now(tz=timezone.utc) + timedelta(hours=1))
    frame = held_frame(hold)
    assert frame["type"] == "confirm_request"
    assert (frame["id"], frame["kind"], frame["round"]) == ("r1", "held", 1)
    assert frame["source"] == {"kind": "workflow", "name": "Weekly summary"}
    assert frame["items"][0]["tool"] == "delete_event"
    assert [a["value"] for a in frame["actions"]] == ["approve", "deny"]


async def test_an_id_that_is_not_a_held_write_is_left_to_the_chat_path() -> None:
    container, conn, *_ = _setup(_hold("r1"))
    assert not await handle_held_confirm(
        {"id": "other", "choice": "approve"}, container, conn, "t1"
    )
    conn.send_frame.assert_not_awaited()


async def test_approving_a_held_write_in_chat_resumes_the_run_once() -> None:
    container, conn, store, run = _setup(_hold("r1"))
    handled = await handle_held_confirm(
        {"id": "r1", "choice": "approve", "edits": {"i2": "new"}}, container, conn, "t1"
    )
    assert handled
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert store.rows["r1"].status is HeldWriteStatus.APPROVED
    assert run.await_args.args[1:] == ("approve", {"i2": "new"})
    conn.send_frame.assert_awaited_with({"type": "confirm_cancel", "id": "r1"}, "t1")

    again = await handle_held_confirm(
        {"id": "r1", "choice": "approve"}, container, conn, "t1"
    )
    assert again
    assert conn.send_frame.await_args.args[0]["detail"] == "No pending confirmation."
    assert run.await_count == 1


async def test_an_invalid_edit_is_rejected_and_nothing_runs() -> None:
    container, conn, store, run = _setup(_hold("r1"))
    await handle_held_confirm(
        {"id": "r1", "choice": "approve", "edits": {"i1": "x"}}, container, conn, "t1"
    )
    assert conn.send_frame.await_args.args[0]["detail"] == "invalid edit"
    assert store.rows["r1"].status is HeldWriteStatus.OPEN
    run.assert_not_awaited()


async def test_connect_replays_open_held_writes() -> None:
    sent: list[dict] = []
    ws = SimpleNamespace(
        send_json=AsyncMock(side_effect=lambda f: sent.append(f)),
        close=AsyncMock(),
    )
    messages = SimpleNamespace(list_unread=AsyncMock(return_value=[]))
    store = MemoryStore(_hold("open"), _hold("done", status=HeldWriteStatus.DENIED))
    await ConnectionManager().connect(ws, messages, held_store=store)
    assert [f["id"] for f in sent] == ["open"]
    assert sent[0]["kind"] == "held"


async def test_handle_confirm_routes_a_held_id_to_the_resumer() -> None:
    from ze_api.api.ws.confirmation import handle_confirm

    container, conn, store, run = _setup(_hold("r1"))
    confirmation_store = AsyncMock()
    confirmation_store.get_pending = AsyncMock(return_value=None)

    result = await handle_confirm(
        SimpleNamespace(),
        {"type": "confirm", "id": "r1", "choice": "approve"},
        container,
        conn,
        None,
        thread_id="t1",
        confirmation_store=confirmation_store,
    )
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert result is None
    assert store.rows["r1"].status is HeldWriteStatus.APPROVED
    run.assert_awaited_once()
    confirmation_store.get_pending.assert_not_awaited()
    conn.send_frame.assert_awaited_with({"type": "confirm_cancel", "id": "r1"}, "t1")


async def test_handle_confirm_leaves_a_chat_confirmation_id_to_the_chat_path() -> None:
    from ze_api.api.ws.confirmation import handle_confirm

    container, conn, store, run = _setup(_hold("r1"))
    confirmation_store = AsyncMock()
    confirmation_store.get_pending = AsyncMock(return_value=None)

    await handle_confirm(
        SimpleNamespace(),
        {"type": "confirm", "id": "chat-req", "choice": "approve"},
        container,
        conn,
        None,
        thread_id="t1",
        confirmation_store=confirmation_store,
    )

    confirmation_store.get_pending.assert_awaited_once_with("chat-req")
    assert conn.send_frame.await_args.args[0]["detail"] == "No pending confirmation."
    assert store.rows["r1"].status is HeldWriteStatus.OPEN
    run.assert_not_awaited()
