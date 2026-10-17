"""Screen context on the message path: parsed once, stored on the user message, replayed on retry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from ze_agents.screen import ScreenContext
from ze_api.api.ws.turns import handle_message
from ze_core.conversation.messages.types import Message

from tests.api.test_ws_retry import _Env, _call, _msg, _trace

WIRE = {
    "place": "doing",
    "origin": "chat_about",
    "subject": [
        {
            "kind": "workflow",
            "id": "w1",
            "label": "Weekly report",
            "as_of": "2026-10-16T09:00:03Z",
        }
    ],
    "compose": "slipping",
    "workspace_placed": [{"path": "a.txt", "size": 4}],
}


def _env():
    container = MagicMock()
    container.translations = None
    container.invoke_raw_turn = AsyncMock(side_effect=RuntimeError("stop after config"))
    msgs = AsyncMock()
    conn = MagicMock()
    conn.take_pending_gate_redirect = MagicMock(return_value=None)
    conn.send_frame = AsyncMock()
    return container, msgs, conn


async def _send(data: dict):
    container, msgs, conn = _env()
    await handle_message(
        MagicMock(),
        {"text": "why?", "thread_id": "t1", **data},
        container,
        msgs,
        conn,
        None,
    )
    saved: Message = msgs.save.await_args.args[0]
    return saved, container.invoke_raw_turn.await_args.kwargs["config_extra"]


async def test_context_is_stored_on_the_user_message_and_passed_typed():
    saved, extra = await _send({"context": WIRE})
    ctx = extra["screen_context"]
    assert isinstance(ctx, ScreenContext)
    assert ctx.subject[0].id == "w1" and ctx.compose == "slipping"
    assert saved.screen_context == ctx.to_wire()
    assert ScreenContext.from_wire(saved.screen_context)[0] == ctx
    assert "screen_context_invalid" not in extra


async def test_no_context_stores_none_and_passes_none():
    saved, extra = await _send({})
    assert saved.screen_context is None
    assert "screen_context" not in extra


async def test_an_invalid_context_still_runs_the_turn_with_warnings_traced():
    saved, extra = await _send(
        {"context": {"place": "attic", "mystery": 1, "subject": ["x"]}}
    )
    assert extra["screen_context_invalid"]
    assert extra.get("user_message_id") == str(saved.id)


async def test_retry_passes_the_stored_context():
    stored = ScreenContext.from_wire(WIRE)[0]
    env = _Env(_trace(_call("web_search", access="read")))
    env.msgs.previous_user_message = AsyncMock(
        return_value=_msg(role="user", text="question", screen_context=stored.to_wire())
    )
    await env.run()
    extra = env.container.invoke_retry_turn.await_args.kwargs["config_extra"]
    assert extra["screen_context"] == stored
    assert "screen_context_invalid" not in extra


async def test_retry_with_no_stored_context_passes_none():
    env = _Env(_trace(_call("web_search", access="read")))
    await env.run()
    extra = env.container.invoke_retry_turn.await_args.kwargs["config_extra"]
    assert "screen_context" not in extra


async def test_retry_with_a_garbage_stored_context_still_proceeds():
    env = _Env(_trace(_call("web_search", access="read")))
    env.msgs.previous_user_message = AsyncMock(
        return_value=_msg(
            role="user",
            text="question",
            screen_context={"place": "attic", "subject": 5},
        )
    )
    await env.run()
    env.container.invoke_retry_turn.assert_awaited_once()
    extra = env.container.invoke_retry_turn.await_args.kwargs["config_extra"]
    assert extra["screen_context_invalid"]
