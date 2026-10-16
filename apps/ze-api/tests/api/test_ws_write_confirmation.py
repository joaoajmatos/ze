"""WebSocket transport of write confirmations (Phase 181, D5)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_agents.park import ConfirmItem, WriteConfirmation
from ze_api.api.ws.confirmation import (
    confirmation_timeout,
    handle_confirm,
    send_confirmation_request,
)
from ze_api.api.ws.connection import ConnectionManager
from ze_api.api.ws.frames import frame_from_pending


def _confirmation(
    request_id: str = "req-1", editable: bool = False
) -> WriteConfirmation:
    return WriteConfirmation(
        request_id=request_id,
        kind="write",
        round=1,
        items=[
            ConfirmItem(
                item_id="i1",
                agent="messenger",
                tool="send_email",
                effect_phrase="send an email",
                summary="to: ana@example.com",
                editable_field="body" if editable else None,
                proposed_text="hello" if editable else None,
                conflict="Ana is on your never-contact list" if editable else None,
            )
        ],
    )


def _outcome(confirmation=None, response="Done.", interrupted=False) -> MagicMock:
    outcome = MagicMock()
    outcome.confirmation = confirmation
    outcome.interrupted = interrupted
    outcome.response = response
    outcome.final_state = {"components": []}
    outcome.config = {"configurable": {"thread_id": "t1"}}
    return outcome


def _container(outcome=None) -> Any:
    container = AsyncMock()
    container.resume_turn = AsyncMock(return_value=outcome or _outcome())
    container.interface = AsyncMock()
    container.interface.send_with_thread = AsyncMock()
    container.settings.confirm_timeout_seconds = 900
    container.notifier = None
    container._build_config = MagicMock(
        return_value={"configurable": {"thread_id": "t1"}}
    )
    return container


async def _connected() -> tuple[Any, ConnectionManager]:
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    mgr = ConnectionManager()
    store = AsyncMock()
    store.list_unread = AsyncMock(return_value=[])
    await mgr.connect(ws, store)
    ws.send_json.reset_mock()
    return ws, mgr


def _frames(ws) -> list[dict]:
    return [c.args[0] for c in ws.send_json.call_args_list]


def _store(confirmation: WriteConfirmation | None = None) -> AsyncMock:
    store = AsyncMock()
    if confirmation is None:
        store.get_pending = AsyncMock(return_value=None)
    else:
        from ze_api.api.ws.frames import confirmation_payload

        store.get_pending = AsyncMock(
            return_value={
                "thread_id": "t1",
                "request_id": confirmation.request_id,
                "prompt": "Ze needs your OK",
                "actions": confirmation_payload(confirmation),
            }
        )
    store.clear = AsyncMock(return_value=True)
    return store


CONFIG = {"configurable": {"thread_id": "t1"}}


async def test_interrupted_turn_sends_items_frame_and_saves_the_row() -> None:
    ws, mgr = await _connected()
    store = AsyncMock()
    confirmation = _confirmation(editable=True)
    outcome = _outcome(confirmation, response=None, interrupted=True)

    request_id, config = await send_confirmation_request(
        mgr, _container(), outcome, "t1", confirmation_store=store
    )

    assert request_id == "req-1" and config == outcome.config
    (frame,) = [f for f in _frames(ws) if f["type"] == "confirm_request"]
    assert frame["id"] == "req-1"
    assert frame["thread_id"] == "t1"
    assert (frame["kind"], frame["round"]) == ("write", 1)
    assert frame["title"]
    assert frame["expires_at"]
    assert [a["value"] for a in frame["actions"]] == ["approve", "deny"]
    assert [a["label"] for a in frame["actions"]] == ["Approve all", "Deny all"]
    (item,) = frame["items"]
    assert item["item_id"] == "i1"
    assert item["effect_phrase"] == "send an email"
    assert item["editable_field"] == "body" and item["proposed_text"] == "hello"
    assert item["conflict"] == "Ana is on your never-contact list"
    assert "prompt" not in frame and "editable" not in frame

    saved = store.save.await_args.kwargs
    assert saved["request_id"] == "req-1" and saved["thread_id"] == "t1"
    assert saved["actions"]["items"][0]["item_id"] == "i1"


async def test_approve_resumes_with_choice_and_empty_edits() -> None:
    ws, mgr = await _connected()
    container = _container()
    store = _store(_confirmation())
    result = await handle_confirm(
        ws,
        {"type": "confirm", "id": "req-1", "choice": "approve"},
        container,
        mgr,
        CONFIG,
        thread_id="t1",
        confirmation_store=store,
    )
    assert result is None
    container.resume_turn.assert_awaited_once_with(
        CONFIG, resume={"choice": "approve", "edits": {}}, request_id="req-1"
    )
    store.clear.assert_awaited_once_with("t1", "req-1")
    container.interface.send_with_thread.assert_awaited_once()
    assert {"type": "typing"} in [
        {k: v for k, v in f.items() if k != "thread_id"} for f in _frames(ws)
    ]


async def test_approve_with_a_valid_edit_resumes_with_it() -> None:
    ws, mgr = await _connected()
    container = _container()
    store = _store(_confirmation(editable=True))
    await handle_confirm(
        ws,
        {"type": "confirm", "id": "req-1", "choice": "approve", "edits": {"i1": "new"}},
        container,
        mgr,
        CONFIG,
        thread_id="t1",
        confirmation_store=store,
    )
    container.resume_turn.assert_awaited_once_with(
        CONFIG, resume={"choice": "approve", "edits": {"i1": "new"}}, request_id="req-1"
    )


@pytest.mark.parametrize("edits", [{"i1": "x"}, {"nope": "x"}])
async def test_edit_for_a_non_editable_or_unknown_item_is_rejected(edits) -> None:
    ws, mgr = await _connected()
    container = _container()
    store = _store(_confirmation(editable=False))
    result = await handle_confirm(
        ws,
        {"type": "confirm", "id": "req-1", "choice": "approve", "edits": edits},
        container,
        mgr,
        CONFIG,
        thread_id="t1",
        confirmation_store=store,
    )
    container.resume_turn.assert_not_awaited()
    store.clear.assert_not_awaited()
    errors = [f for f in _frames(ws) if f["type"] == "error"]
    assert errors and errors[0]["detail"] == "invalid edit"
    assert result == ("req-1", CONFIG)  # the confirmation stays open


async def test_deny_resumes_the_graph_without_aborting_the_checkpoint() -> None:
    ws, mgr = await _connected()
    container = _container(_outcome(response="Okay, I didn't send an email."))
    store = _store(_confirmation())
    result = await handle_confirm(
        ws,
        {"type": "confirm", "id": "req-1", "choice": "deny"},
        container,
        mgr,
        CONFIG,
        thread_id="t1",
        confirmation_store=store,
    )
    assert result is None
    container.resume_turn.assert_awaited_once_with(
        CONFIG, resume={"choice": "deny", "edits": {}}, request_id="req-1"
    )
    container.abort_pending_checkpoint.assert_not_awaited()
    sent = container.interface.send_with_thread.await_args
    assert sent.args[0] == "Okay, I didn't send an email."


async def test_resume_that_parks_again_opens_the_next_round() -> None:
    ws, mgr = await _connected()
    nxt = _confirmation("req-2")
    nxt.round = 2
    container = _container(_outcome(nxt, response=None, interrupted=True))
    store = _store(_confirmation())
    result = await handle_confirm(
        ws,
        {"type": "confirm", "id": "req-1", "choice": "approve"},
        container,
        mgr,
        CONFIG,
        thread_id="t1",
        confirmation_store=store,
    )
    assert result == ("req-2", container.resume_turn.return_value.config)
    frames = [f for f in _frames(ws) if f["type"] == "confirm_request"]
    assert [f["id"] for f in frames] == ["req-2"] and frames[0]["round"] == 2


async def test_unknown_or_cleared_id_is_rejected_and_nothing_runs() -> None:
    ws, mgr = await _connected()
    container = _container()
    store = _store(None)
    result = await handle_confirm(
        ws,
        {"type": "confirm", "id": "gone", "choice": "approve"},
        container,
        mgr,
        CONFIG,
        thread_id="t1",
        confirmation_store=store,
    )
    assert result is None
    container.resume_turn.assert_not_awaited()
    errors = [f for f in _frames(ws) if f["type"] == "error"]
    assert errors[0]["detail"] == "No pending confirmation."


async def test_missing_in_memory_config_is_rebuilt_from_the_thread() -> None:
    """After a server restart the row survives; the answer still resumes the graph."""
    ws, mgr = await _connected()
    container = _container()
    store = _store(_confirmation())
    await handle_confirm(
        ws,
        {"type": "confirm", "id": "req-1", "choice": "approve"},
        container,
        mgr,
        None,
        thread_id="t1",
        confirmation_store=store,
    )
    container._build_config.assert_called_once_with("t1")
    container.resume_turn.assert_awaited_once()


async def test_busy_thread_keeps_the_confirmation_open() -> None:
    ws, mgr = await _connected()
    mgr.try_set_busy("t1")
    container = _container()
    store = _store(_confirmation())
    result = await handle_confirm(
        ws,
        {"type": "confirm", "id": "req-1", "choice": "approve"},
        container,
        mgr,
        CONFIG,
        thread_id="t1",
        confirmation_store=store,
    )
    assert result == ("req-1", CONFIG)
    container.resume_turn.assert_not_awaited()
    store.clear.assert_not_awaited()


async def test_timeout_resumes_as_a_denial_and_delivers_the_reply() -> None:
    ws, mgr = await _connected()
    container = _container(_outcome(response="Okay, I didn't send an email."))
    store = _store(_confirmation())
    await confirmation_timeout(
        store, mgr, None, "t1", 0, "req-1", container=container, graph_config=CONFIG
    )
    container.resume_turn.assert_awaited_once_with(
        CONFIG, resume={"choice": "timeout"}, request_id="req-1"
    )
    container.abort_pending_checkpoint.assert_not_awaited()
    container.interface.send_with_thread.assert_awaited_once()
    cancel = [f for f in _frames(ws) if f["type"] == "confirm_cancel"]
    assert cancel and cancel[0]["id"] == "req-1"


async def test_timeout_after_the_row_was_cleared_does_nothing() -> None:
    ws, mgr = await _connected()
    container = _container()
    store = _store(_confirmation())
    store.clear = AsyncMock(return_value=False)
    await confirmation_timeout(
        store, mgr, None, "t1", 0, "req-1", container=container, graph_config=CONFIG
    )
    container.resume_turn.assert_not_awaited()
    assert _frames(ws) == []


async def test_reconnect_replays_the_items_frame() -> None:
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    mgr = ConnectionManager()
    msgs = AsyncMock()
    msgs.list_unread = AsyncMock(return_value=[])
    store = AsyncMock()
    from ze_api.api.ws.frames import confirmation_payload

    store.get_all_pending = AsyncMock(
        return_value=[
            {
                "thread_id": "t1",
                "request_id": "req-1",
                "prompt": "Ze needs your OK",
                "actions": confirmation_payload(_confirmation()),
                "expires_at": None,
            }
        ]
    )
    await mgr.connect(ws, msgs, store)
    (frame,) = [f for f in _frames(ws) if f["type"] == "confirm_request"]
    assert frame == frame_from_pending(store.get_all_pending.return_value[0])
    assert frame["items"][0]["tool"] == "send_email"
    assert frame["thread_id"] == "t1" and frame["kind"] == "write"


async def test_a_new_turn_clears_open_confirmations_and_records_them_as_superseded() -> (
    None
):
    from ze_agents.park import WriteConfirmation  # noqa: F401
    from ze_api.api.ws.frames import confirmation_payload
    from ze_api.api.ws.turns import handle_message
    from ze_core.conversation.messages.types import MessageTrace

    ws, mgr = await _connected()
    trace = MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=1.0,
        score_gap=1.0,
        is_compound=False,
        subtasks=[],
    )
    outcome = _outcome(response="Fresh answer")
    outcome.final_state = {"components": [], "message_trace": trace}
    outcome.message_id = ""
    container = _container(outcome)
    container.invoke_raw_turn = AsyncMock(return_value=outcome)
    container.translations = None
    store = _store(_confirmation())
    store.get_pending_for_thread = AsyncMock(
        return_value=[
            {
                "thread_id": "t1",
                "request_id": "req-1",
                "actions": confirmation_payload(_confirmation()),
            }
        ]
    )
    await handle_message(
        ws,
        {"text": "never mind", "thread_id": "t1"},
        container,
        AsyncMock(),
        mgr,
        None,
        confirmation_store=store,
    )
    store.clear.assert_awaited_with("t1", "req-1")
    assert [r["outcome"] for r in trace.write_confirmations] == ["superseded"]
    assert trace.write_confirmations[0]["tool"] == "send_email"
    cancels = [f for f in _frames(ws) if f["type"] == "confirm_cancel"]
    assert cancels and cancels[0]["id"] == "req-1"


@pytest.mark.parametrize("choice", ["approve", "deny"])
async def test_an_answer_cancels_the_card_on_every_client(choice) -> None:
    ws, mgr = await _connected()
    store = _store(_confirmation())

    await handle_confirm(
        ws,
        {"type": "confirm", "id": "req-1", "choice": choice},
        _container(),
        mgr,
        CONFIG,
        thread_id="t1",
        confirmation_store=store,
    )

    assert {
        "type": "confirm_cancel",
        "id": "req-1",
        "reason": "answered",
        "thread_id": "t1",
    } in _frames(ws)
