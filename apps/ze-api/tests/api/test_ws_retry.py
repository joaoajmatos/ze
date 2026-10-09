"""WebSocket retry handler: server-side eligibility, atomic replace, failure safety."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze_agents.errors import RetryFailedError
from ze_api.api.websocket.turns import handle_retry
from ze_core.conversation.messages.types import Message, MessageTrace, ToolCallTrace
from ze_memory.feedback_records import FeedbackKind


def _msg(role="assistant", thread="t1", text="reply", **kw) -> Message:
    return Message(
        id=kw.pop("id", uuid4()),
        role=role,
        text=text,
        components=[],
        read=True,
        created_at=datetime.now(timezone.utc),
        thread_id=thread,
        **kw,
    )


def _call(name, **kw) -> ToolCallTrace:
    base = dict(name=name, result_snippet="", duration_ms=1, success=True)
    base.update(kw)
    return ToolCallTrace(**base)


def _trace(*calls, known=True) -> MessageTrace:
    return MessageTrace(
        agent="research",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.1,
        is_compound=False,
        subtasks=[],
        tool_calls=list(calls),
        effects_known=known,
    )


class _Env:
    def __init__(self, trace, message=None, *, user_text="question"):
        self.message = message or _msg()
        self.msgs = AsyncMock()
        self.msgs.get_message = AsyncMock(return_value=self.message)
        self.msgs.get_trace = AsyncMock(return_value=trace)
        self.msgs.latest_assistant_id = AsyncMock(return_value=self.message.id)
        self.msgs.previous_user_message = AsyncMock(
            return_value=_msg(role="user", text=user_text)
        )
        self.msgs.mark_superseded = AsyncMock(return_value=True)
        self.feedback = AsyncMock()
        self.feedback.append = AsyncMock()
        self.conf = AsyncMock()
        self.conf.get_pending_for_thread = AsyncMock(return_value=[])
        self.conn = MagicMock()
        self.conn.is_busy = MagicMock(return_value=True)  # the retry's own flag
        self.conn.send_frame = AsyncMock()
        self.new_id = uuid4()
        self.container = MagicMock()
        self.container.is_thread_locked = MagicMock(return_value=False)
        self.container.translations = None
        self.container.interface.send_with_thread = AsyncMock()
        self.container.invoke_retry_turn = AsyncMock(
            return_value=SimpleNamespace(
                response="fresh",
                message_id=str(self.new_id),
                config={"configurable": {"thread_id": "t1"}},
                final_state={"components": [], "message_trace": _trace()},
            )
        )

    async def run(self, message_id=None):
        await handle_retry(
            {
                "type": "retry",
                "message_id": str(message_id or self.message.id),
                "thread_id": "t1",
            },
            self.container,
            self.msgs,
            self.conn,
            feedback_store=self.feedback,
            confirmation_store=self.conf,
        )

    def frames(self):
        return [c.args[0] for c in self.conn.send_frame.await_args_list]

    def errors(self):
        return [f for f in self.frames() if f["type"] == "error"]


async def test_text_only_retry_replaces_reply():
    env = _Env(_trace(_call("web_search", access="read")))
    await env.run()

    env.container.invoke_retry_turn.assert_awaited_once()
    assert env.container.invoke_retry_turn.await_args.args[:2] == ("t1", "question")
    send = env.container.interface.send_with_thread
    assert send.await_args.kwargs["replaces"] == env.message.id
    assert send.await_args.kwargs["message_id"] == str(env.new_id)
    env.msgs.mark_superseded.assert_awaited_once_with(env.message.id, env.new_id)
    sup = [f for f in env.frames() if f["type"] == "message_superseded"]
    assert sup == [
        {
            "type": "message_superseded",
            "message_id": str(env.message.id),
            "replaced_by": str(env.new_id),
        }
    ]
    assert env.errors() == []


async def test_retry_requested_is_recorded_before_the_run():
    env = _Env(_trace())
    await env.run()
    draft = env.feedback.append.await_args.args[0].feedback_record
    assert draft.kind is FeedbackKind.RETRY_REQUESTED
    assert draft.message_id == env.message.id
    assert draft.kind is not FeedbackKind.THUMBS_DOWN


async def test_failed_run_changes_nothing_and_reports_retry_failed():
    env = _Env(_trace())
    env.container.invoke_retry_turn = AsyncMock(side_effect=RetryFailedError("boom"))
    await env.run()
    env.container.interface.send_with_thread.assert_not_awaited()
    env.msgs.mark_superseded.assert_not_awaited()
    [err] = env.errors()
    assert err["code"] == "retry_failed"
    assert err["message_id"] == str(env.message.id)
    # the request is still evidence even though the run failed
    env.feedback.append.assert_awaited_once()


async def test_unexpected_exception_also_reports_retry_failed():
    env = _Env(_trace())
    env.container.invoke_retry_turn = AsyncMock(side_effect=RuntimeError("x"))
    await env.run()
    assert env.errors()[0]["code"] == "retry_failed"
    env.msgs.mark_superseded.assert_not_awaited()


async def test_supersede_failure_is_reported_not_swallowed():
    env = _Env(_trace())
    env.msgs.mark_superseded = AsyncMock(return_value=False)
    await env.run()
    assert env.errors()[0]["code"] == "retry_failed"
    assert not [f for f in env.frames() if f["type"] == "message_superseded"]


# ── ineligible classes: refused before any graph run (T038) ──────────────────

_REFUSALS = [
    (
        "has_reversible_action",
        _trace(
            _call(
                "set_reminder",
                access="write",
                reversibility="reversible",
                effect_phrase="set a reminder",
            )
        ),
    ),
    (
        "has_irreversible_action",
        _trace(
            _call(
                "send_email",
                access="write",
                reversibility="irreversible",
                effect_phrase="sent an email",
            )
        ),
    ),
    ("has_write_action", _trace(_call("legacy", access="write"))),
    (
        "confirmed_action",
        _trace(
            _call(
                "send_email",
                access="write",
                reversibility="irreversible",
                gate="approved",
            )
        ),
    ),
    ("unknown_tool", _trace(_call("mystery", access="unknown"))),
    ("unknown_tool", _trace(known=False)),
    ("trace_unavailable", None),
]


@pytest.mark.parametrize(("code", "trace"), _REFUSALS)
async def test_hand_built_retry_is_refused_with_the_same_reason(code, trace):
    env = _Env(trace)
    await env.run()
    env.container.invoke_retry_turn.assert_not_awaited()
    env.feedback.append.assert_not_awaited()
    [err] = env.errors()
    assert err["code"] == "retry_unavailable"
    assert err["reason_code"] == code
    assert err["reason_text"]


async def test_workspace_run_is_refused():
    from ze_core.conversation.messages.types import WorkspaceUsageTrace

    trace = _trace(_call("workspace_run", access="write", reversibility="irreversible"))
    trace.workspace = WorkspaceUsageTrace(runs=[{"command": "ls"}])
    env = _Env(trace)
    await env.run()
    assert env.errors()[0]["reason_code"] == "workspace_run"
    env.container.invoke_retry_turn.assert_not_awaited()


async def test_not_latest_is_refused():
    env = _Env(_trace())
    env.msgs.latest_assistant_id = AsyncMock(return_value=uuid4())
    await env.run()
    assert env.errors()[0]["reason_code"] == "not_latest"
    env.container.invoke_retry_turn.assert_not_awaited()


async def test_thread_lock_held_by_another_turn_is_busy():
    env = _Env(_trace())
    env.container.is_thread_locked = MagicMock(return_value=True)
    await env.run()
    assert env.errors()[0]["reason_code"] == "busy"
    env.container.invoke_retry_turn.assert_not_awaited()


async def test_pending_confirmation_is_turn_pending():
    env = _Env(_trace())
    env.conf.get_pending_for_thread = AsyncMock(return_value=[{"request_id": "r"}])
    await env.run()
    assert env.errors()[0]["reason_code"] == "turn_pending"


# ── per-delegate confirmations (Phase 152) ───────────────────────────────────


async def test_denied_delegate_write_is_not_an_action():
    env = _Env(
        _trace(
            _call("delegate_to_agent", access="delegate", gate="denied", success=False),
            _call(
                "send_email",
                access="write",
                reversibility="irreversible",
                gate="denied",
                success=False,
            ),
        )
    )
    await env.run()
    env.container.invoke_retry_turn.assert_awaited_once()


async def test_expired_gate_is_not_an_action():
    env = _Env(
        _trace(
            _call(
                "send_email",
                access="write",
                reversibility="irreversible",
                gate="expired",
                success=False,
            )
        )
    )
    await env.run()
    env.container.invoke_retry_turn.assert_awaited_once()


async def test_two_concurrent_gates_one_approved_blocks():
    env = _Env(
        _trace(
            _call(
                "send_email",
                access="write",
                reversibility="irreversible",
                gate="denied",
                success=False,
            ),
            _call(
                "set_reminder",
                access="write",
                reversibility="reversible",
                gate="approved",
            ),
        )
    )
    await env.run()
    assert env.errors()[0]["reason_code"] == "confirmed_action"


# ── input validation ─────────────────────────────────────────────────────────


async def test_invalid_message_id_is_rejected():
    env = _Env(_trace())
    await handle_retry(
        {"type": "retry", "message_id": "nope", "thread_id": "t1"},
        env.container, env.msgs, env.conn,
        feedback_store=env.feedback, confirmation_store=env.conf,
    )  # fmt: skip
    assert env.errors()[0]["code"] == "retry_unavailable"


async def test_user_message_or_wrong_thread_is_rejected():
    env = _Env(_trace(), _msg(role="user"))
    await env.run()
    assert env.errors()[0]["code"] == "retry_unavailable"
    env2 = _Env(_trace(), _msg(thread="other"))
    await env2.run()
    assert env2.errors()[0]["code"] == "retry_unavailable"
    env2.container.invoke_retry_turn.assert_not_awaited()
