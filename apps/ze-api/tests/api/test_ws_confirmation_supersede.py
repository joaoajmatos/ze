"""A superseded or already-answered confirmation cannot answer another (Phase 181, review H4/M5)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from ze_agents.park import ConfirmItem, WriteConfirmation
from ze_api.api.ws.confirmation import (
    confirmation_timeout,
    handle_confirm,
    send_confirmation_request,
)
from ze_api.api.ws.connection import ConnectionManager
from ze_api.api.ws.frames import confirmation_payload
from ze_core.conversation.turn import NO_PENDING_CONFIRMATION

CONFIG = {"configurable": {"thread_id": "t1"}}


def _confirmation(request_id: str) -> WriteConfirmation:
    return WriteConfirmation(
        request_id=request_id,
        kind="write",
        round=1,
        items=[
            ConfirmItem(
                item_id=f"{request_id}-i1",
                agent="messenger",
                tool="send_email",
                effect_phrase="send an email",
                summary="to: ana@example.com",
            )
        ],
    )


def _outcome(confirmation=None, *, response="Done.", error=None) -> MagicMock:
    outcome = MagicMock()
    outcome.confirmation = confirmation
    outcome.interrupted = confirmation is not None
    outcome.response = response
    outcome.error = error
    outcome.final_state = {"components": []}
    outcome.config = CONFIG
    return outcome


def _container(outcome=None) -> Any:
    container = AsyncMock()
    container.resume_turn = AsyncMock(return_value=outcome or _outcome())
    container.interface = AsyncMock()
    container.settings.confirm_timeout_seconds = 900
    container.notifier = None
    container._build_config = MagicMock(
        side_effect=lambda thread_id: {"configurable": {"thread_id": thread_id}}
    )
    return container


def _row(request_id: str, thread_id: str = "t1") -> dict:
    return {
        "thread_id": thread_id,
        "request_id": request_id,
        "prompt": "Ze needs your OK",
        "actions": confirmation_payload(_confirmation(request_id)),
    }


def _store(*rows: dict) -> AsyncMock:
    by_id = {row["request_id"]: row for row in rows}
    store = AsyncMock()
    store.get_pending = AsyncMock(side_effect=lambda rid: by_id.get(rid))
    store.get_pending_for_thread = AsyncMock(return_value=list(rows))
    store.clear = AsyncMock(return_value=True)
    return store


async def _connected() -> tuple[Any, ConnectionManager]:
    ws = AsyncMock()
    mgr = ConnectionManager()
    store = AsyncMock()
    store.list_unread = AsyncMock(return_value=[])
    await mgr.connect(ws, store)
    ws.send_json.reset_mock()
    return ws, mgr


def _frames(ws) -> list[dict]:
    return [c.args[0] for c in ws.send_json.call_args_list]


async def _confirm(ws, mgr, container, store, request_id="req-1", **kw):
    return await handle_confirm(
        ws,
        {"type": "confirm", "id": request_id, "choice": "approve"},
        container,
        mgr,
        kw.get("pending_config", CONFIG),
        thread_id=kw.get("thread_id", "t1"),
        confirmation_store=store,
    )


async def test_a_turn_that_parks_clears_the_older_open_confirmation() -> None:
    ws, mgr = await _connected()
    store = _store(_row("old"))
    outcome = _outcome(_confirmation("new"), response=None)

    await send_confirmation_request(
        mgr, _container(), outcome, "t1", confirmation_store=store
    )

    store.clear.assert_any_await("t1", "old")
    assert {"type": "confirm_cancel", "id": "old"} in [
        {k: v for k, v in f.items() if k != "thread_id"} for f in _frames(ws)
    ]
    assert store.save.await_args.kwargs["request_id"] == "new"


async def test_confirm_resumes_only_the_confirmation_it_names() -> None:
    ws, mgr = await _connected()
    container = _container()
    store = _store(_row("req-1"))

    await _confirm(ws, mgr, container, store)

    assert container.resume_turn.await_args.kwargs["request_id"] == "req-1"


async def test_a_stale_id_answering_a_newer_confirmation_is_rejected() -> None:
    ws, mgr = await _connected()
    container = _container(_outcome(response=None, error=NO_PENDING_CONFIRMATION))
    store = _store(_row("old"))

    await _confirm(ws, mgr, container, store, request_id="old")

    container.interface.send_with_thread.assert_not_awaited()
    errors = [f["detail"] for f in _frames(ws) if f["type"] == "error"]
    assert errors == ["No pending confirmation."]


async def test_confirm_does_not_resume_when_another_answer_cleared_the_row() -> None:
    ws, mgr = await _connected()
    container = _container()
    store = _store(_row("req-1"))
    store.clear = AsyncMock(return_value=False)

    await _confirm(ws, mgr, container, store)

    container.resume_turn.assert_not_awaited()
    errors = [f["detail"] for f in _frames(ws) if f["type"] == "error"]
    assert errors == ["No pending confirmation."]
    assert not mgr.is_busy("t1")


async def test_the_resume_config_comes_from_the_stored_row() -> None:
    ws, mgr = await _connected()
    container = _container()
    store = _store(_row("req-1", thread_id="t1"))

    await _confirm(ws, mgr, container, store, pending_config=None, thread_id="other")

    container._build_config.assert_called_once_with("t1")
    assert container.resume_turn.await_args.args[0] == CONFIG


async def test_timeout_resumes_only_its_own_confirmation() -> None:
    ws, mgr = await _connected()
    container = _container(_outcome(response="Okay, I didn't send an email."))
    store = _store(_row("req-1"))

    await confirmation_timeout(
        store, mgr, None, "t1", 0, "req-1", container=container, graph_config=CONFIG
    )

    assert container.resume_turn.await_args.kwargs["request_id"] == "req-1"
    assert not mgr.is_busy("t1")


async def test_timeout_on_a_busy_thread_does_not_resume() -> None:
    ws, mgr = await _connected()
    mgr.try_set_busy("t1")
    container = _container()
    store = _store(_row("req-1"))

    await confirmation_timeout(
        store, mgr, None, "t1", 0, "req-1", container=container, graph_config=CONFIG
    )

    container.resume_turn.assert_not_awaited()


async def test_the_confirmation_push_targets_the_thread_of_the_paused_turn() -> None:
    import asyncio

    ws, mgr = await _connected()
    container = _container()
    container.notifier = AsyncMock()
    outcome = _outcome(_confirmation("new"), response=None)

    await send_confirmation_request(
        mgr, container, outcome, "t1", confirmation_store=_store()
    )
    await asyncio.sleep(0)

    kwargs = container.notifier.notify.await_args.kwargs
    assert (kwargs["target_type"], kwargs["target_id"]) == ("chat_thread", "t1")
