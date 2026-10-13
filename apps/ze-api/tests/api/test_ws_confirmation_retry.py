"""A retry that paused at a confirmation resolves into a superseding reply (Phase 180 T028)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from tests.api.test_ws_retry import _msg, _trace
from ze_api.api.websocket import confirmation
from ze_api.api.websocket.confirmation import (
    confirmation_timeout,
    handle_confirm,
    send_confirmation_request,
)
from ze_core.conversation.messages.types import RollbackEntry, RollbackRecord


def _record(state="rolled_back_awaiting_confirmation") -> RollbackRecord:
    return RollbackRecord(
        state=state,
        entries=[
            RollbackEntry(
                entry_id="e0",
                call_index=0,
                tool="set_reminder",
                undo_tool="cancel_reminder",
                effect_phrase="set a reminder",
                outcome="undone",
                at="t",
            )
        ],
        started_at="t",
        updated_at="t",
    )


class _Env:
    def __init__(self, *, with_record=True, response="after deny"):
        self.old = _msg(rollback=_record() if with_record else None)
        self.new_id = uuid4()
        self.config = {
            "configurable": {
                "thread_id": "t1",
                "retry_mode": True,
                "retry_replaces": str(self.old.id),
            }
        }
        self.msgs = AsyncMock()
        self.msgs.get_message = AsyncMock(return_value=self.old)
        self.msgs.mark_superseded = AsyncMock(return_value=True)
        self.msgs.set_rollback = AsyncMock()
        self.conn = MagicMock()
        self.conn.send_frame = AsyncMock()
        self.conn.try_set_busy = MagicMock(return_value=True)
        self.conn.clear_busy = MagicMock()
        self.store = AsyncMock()
        self.container = MagicMock()
        self.container.message_store = self.msgs

        async def _send(*args, after_save=None, **kw):
            if after_save is not None and not await after_save():
                return False
            return True

        self.container.interface.send_with_thread = AsyncMock(side_effect=_send)
        self.outcome = SimpleNamespace(
            response=response,
            interrupted=False,
            message_id=str(self.new_id),
            config=self.config,
            final_state={"components": [], "message_trace": _trace()},
        )
        self.container.resume_turn = AsyncMock(return_value=self.outcome)
        self.container.graph.aget_state = AsyncMock(
            return_value=SimpleNamespace(interrupts=[()])
        )
        self.container.abort_pending_checkpoint = AsyncMock()

    async def confirm(self, choice):
        return await handle_confirm(
            MagicMock(),
            {"type": "confirm", "id": "req-1", "choice": choice},
            self.container,
            self.conn,
            self.config,
            thread_id="t1",
            confirmation_store=self.store,
            msg_store=self.msgs,
        )

    def frames(self):
        return [c.args[0] for c in self.conn.send_frame.await_args_list]

    def types(self):
        return [f["type"] for f in self.frames()]

    def states(self):
        return [c.args[1].state for c in self.msgs.set_rollback.await_args_list]


async def test_approve_saves_the_reply_with_replaces_and_supersedes():
    env = _Env()
    await env.confirm("approve")
    sent = env.container.interface.send_with_thread.await_args.kwargs
    assert sent["replaces"] == env.old.id
    assert sent["message_id"] == str(env.new_id)
    env.msgs.mark_superseded.assert_awaited_once_with(env.old.id, env.new_id)
    assert env.states() == ["superseded"]
    assert env.msgs.set_rollback.await_args.args[1].replaced_by == str(env.new_id)
    assert "message_superseded" in env.types()
    last = [f for f in env.frames() if f["type"] == "message_rollback"][-1]
    assert last["rollback"]["state"] == "superseded"
    assert sent["trace"].rollback.replaces == str(env.old.id)


async def test_deny_with_a_produced_reply_still_supersedes():
    env = _Env()
    await env.confirm("deny")
    sent = env.container.interface.send_with_thread.await_args.kwargs
    assert sent["replaces"] == env.old.id
    env.msgs.mark_superseded.assert_awaited_once_with(env.old.id, env.new_id)
    assert env.states() == ["superseded"]
    assert "message_superseded" in env.types()


async def test_deny_without_a_reply_marks_retry_failed_and_keeps_the_old_reply():
    env = _Env(response="")
    await env.confirm("deny")
    env.container.interface.send_with_thread.assert_not_awaited()
    env.msgs.mark_superseded.assert_not_awaited()
    assert env.states() == ["rolled_back_retry_failed"]
    rolled = [f for f in env.frames() if f["type"] == "message_rollback"]
    assert rolled[-1]["rollback"]["state"] == "rolled_back_retry_failed"
    assert "message_superseded" not in env.types()


async def test_deny_abort_path_marks_retry_failed():
    env = _Env()
    env.container.graph.aget_state = AsyncMock(
        return_value=SimpleNamespace(interrupts=[])
    )
    await env.confirm("deny")
    env.container.abort_pending_checkpoint.assert_awaited_once()
    assert env.states() == ["rolled_back_retry_failed"]
    assert "confirm_cancel" in env.types()
    env.msgs.mark_superseded.assert_not_awaited()


async def test_resume_error_marks_retry_failed():
    env = _Env()
    env.container.resume_turn = AsyncMock(side_effect=RuntimeError("boom"))
    await env.confirm("approve")
    assert env.states() == ["rolled_back_retry_failed"]


async def test_second_gate_keeps_the_retry_pending():
    env = _Env()
    env.outcome.response = None
    env.outcome.interrupted = True
    gate = ("req-2", env.config)
    with patch.object(
        confirmation, "send_confirmation_request", AsyncMock(return_value=gate)
    ):
        result = await env.confirm("approve")
    assert result == gate
    env.msgs.set_rollback.assert_not_awaited()


async def test_text_only_retry_with_no_record_supersedes_without_a_rollback_write():
    env = _Env(with_record=False)
    await env.confirm("approve")
    env.msgs.mark_superseded.assert_awaited_once()
    env.msgs.set_rollback.assert_not_awaited()
    assert "message_rollback" not in env.types()
    assert "message_superseded" in env.types()


async def test_failed_supersede_is_reported():
    env = _Env()
    env.msgs.mark_superseded = AsyncMock(return_value=False)
    await env.confirm("approve")
    assert "message_superseded" not in env.types()
    assert any(f.get("detail") == "Resume failed." for f in env.frames())


async def test_a_plain_confirmation_is_untouched():
    env = _Env()
    env.config = {"configurable": {"thread_id": "t1"}}
    await env.confirm("approve")
    sent = env.container.interface.send_with_thread.await_args.kwargs
    assert "replaces" not in sent
    env.msgs.mark_superseded.assert_not_awaited()
    env.msgs.set_rollback.assert_not_awaited()


async def test_expiry_marks_a_paused_retry_failed():
    env = _Env()
    env.store.clear = AsyncMock(return_value=True)
    await confirmation_timeout(
        env.store,
        env.conn,
        None,
        "t1",
        0,
        "req-1",
        container=env.container,
        graph_config=env.config,
    )
    assert env.states() == ["rolled_back_retry_failed"]
    assert "message_rollback" in env.types()


async def test_expiry_of_an_ordinary_gate_touches_nothing():
    env = _Env()
    env.store.clear = AsyncMock(return_value=True)
    await confirmation_timeout(
        env.store,
        env.conn,
        None,
        "t1",
        0,
        "req-1",
        container=env.container,
        graph_config={"configurable": {"thread_id": "t1"}},
    )
    env.msgs.set_rollback.assert_not_awaited()


async def test_pending_confirmation_config_keeps_the_retry_keys():
    env = _Env()
    env.container.settings = SimpleNamespace(confirm_timeout_seconds=900)
    env.container.notifier = None
    outcome = SimpleNamespace(
        confirm_request_id="req-7",
        draft="Send it?",
        confirm_editable=False,
        confirm_proposed="",
        config=env.config,
    )
    with patch("asyncio.create_task", side_effect=lambda coro: coro.close()):
        request_id, config = await send_confirmation_request(
            env.conn, env.container, outcome, "t1", confirmation_store=env.store
        )
    assert request_id == "req-7"
    assert config["configurable"]["retry_mode"] is True
    assert config["configurable"]["retry_replaces"] == str(env.old.id)


async def test_reply_then_second_gate_does_not_supersede_twice():
    env = _Env()
    env.outcome.interrupted = True
    seen = {}

    async def _fake_send(conn_mgr, container, outcome, thread_id, **kw):
        seen["config"] = outcome.config
        return "req-2", outcome.config

    with patch.object(confirmation, "send_confirmation_request", _fake_send):
        await env.confirm("approve")
    env.msgs.mark_superseded.assert_awaited_once()
    assert "retry_replaces" not in seen["config"]["configurable"]
    assert "retry_mode" not in seen["config"]["configurable"]
