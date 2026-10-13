"""Retry with rollback: plan guard, consent, executor, record, honest failures (Phase 180 T027)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from tests.api.test_ws_retry import _Env, _call, _msg, _trace
from ze_agents.errors import RetryFailedError
from ze_api.api.websocket import turns
from ze_api.api.websocket.endpoint import _retry_crash_frame, _run_retry_task
from ze_api.api.websocket.turns import handle_retry
from ze_core.conversation.messages.types import (
    RollbackEntry,
    RollbackRecord,
)
from ze_core.conversation.retry import retry_eligibility


def _reminder(call_index=0, rid="r1"):
    return _call(
        "set_reminder",
        access="write",
        reversibility="reversible",
        effect_phrase="set a reminder",
        undo_tool="cancel_reminder",
        agent="reminders",
        undo_args={"reminder_id": rid},
        undo_note="Does not recall a shown notification",
        call_index=call_index,
    )


def _entry(i=0, outcome="undone", phrase="set a reminder", code=None):
    return RollbackEntry(
        entry_id=f"e{i}",
        call_index=i,
        tool="set_reminder",
        undo_tool="cancel_reminder",
        effect_phrase=phrase,
        outcome=outcome,
        at="t",
        failure_code=code,
    )


def _record(state, *entries):
    return RollbackRecord(
        state=state, entries=list(entries), started_at="t", updated_at="t"
    )


def _plan_ids(env) -> list[str]:
    elig = retry_eligibility(
        env.message,
        env.trace,
        latest_assistant_id=env.message.id,
    )
    return [e.entry_id for e in elig.plan]


class _RbEnv(_Env):
    def __init__(self, *calls, rollback=None, **kw):
        trace = _trace(*calls)
        message = kw.pop("message", None) or _msg(rollback=rollback)
        super().__init__(trace, message, **kw)
        self.trace = trace
        self.msgs.set_rollback = AsyncMock()

    async def run_with(self, confirmed=None):
        frame = {
            "type": "retry",
            "message_id": str(self.message.id),
            "thread_id": "t1",
        }
        if confirmed is not None:
            frame["confirmed_plan"] = confirmed
        return await handle_retry(
            frame,
            self.container,
            self.msgs,
            self.conn,
            feedback_store=self.feedback,
            confirmation_store=self.conf,
        )

    def frame_types(self):
        return [f["type"] for f in self.frames()]

    def stored_states(self):
        return [c.args[1].state for c in self.msgs.set_rollback.await_args_list]


def _patch_rollback(record):
    return patch.object(turns, "run_rollback", AsyncMock(return_value=record))


async def test_plan_without_confirmation_is_refused_and_changes_nothing():
    env = _RbEnv(_reminder())
    with _patch_rollback(_record("rolled_back_retry_failed")) as rb:
        await env.run_with(confirmed=None)
    [err] = env.errors()
    assert err["code"] == "retry_unavailable"
    assert err["reason_code"] == "undo_not_confirmed"
    rb.assert_not_awaited()
    env.container.invoke_retry_turn.assert_not_awaited()
    env.feedback.append.assert_not_awaited()


async def test_stale_plan_is_refused_with_the_recomputed_public_plan():
    env = _RbEnv(_reminder())
    with _patch_rollback(_record("rolled_back_retry_failed")) as rb:
        await env.run_with(confirmed=["stale-entry"])
    [err] = env.errors()
    assert err["reason_code"] == "plan_changed"
    assert [e["entry_id"] for e in err["plan"]] == _plan_ids(env)
    assert set(err["plan"][0]) == {"entry_id", "tool", "effect_phrase", "undo_note"}
    assert "r1" not in str(err)
    rb.assert_not_awaited()
    env.container.invoke_retry_turn.assert_not_awaited()
    env.feedback.append.assert_not_awaited()
    env.msgs.set_rollback.assert_not_awaited()


async def test_confirming_entries_that_no_longer_exist_is_plan_changed():
    env = _RbEnv()
    await env.run_with(confirmed=["gone"])
    assert env.errors()[0]["reason_code"] == "plan_changed"
    assert env.errors()[0]["plan"] == []


async def test_confirmed_subset_or_wrong_order_is_plan_changed():
    env = _RbEnv(_reminder(0, "a"), _reminder(1, "b"))
    ids = _plan_ids(env)
    for bad in (ids[:1], list(reversed(ids)), ids + ["x"]):
        env.conn.send_frame.reset_mock()
        await env.run_with(confirmed=bad)
        assert env.errors()[0]["reason_code"] == "plan_changed"


async def test_full_rollback_then_regeneration_supersedes():
    env = _RbEnv(_reminder())
    ids = _plan_ids(env)
    done = _record("rolled_back_retry_failed", _entry())
    with _patch_rollback(done) as rb:
        result = await env.run_with(confirmed=ids)
    assert result is None
    rb.assert_awaited_once()
    assert rb.await_args.kwargs["message_id"] == env.message.id
    assert [e.entry_id for e in rb.await_args.args[0]] == ids
    env.feedback.append.assert_awaited_once()
    env.container.invoke_retry_turn.assert_awaited_once()
    assert env.errors() == []
    types = env.frame_types()
    assert types.index("message_rollback") < types.index("message_superseded")
    sent = env.container.interface.send_with_thread.await_args.kwargs
    assert sent["trace"].rollback.replaces == str(env.message.id)
    assert [e.outcome for e in sent["trace"].rollback.entries] == ["undone"]
    assert env.stored_states() == ["superseded"]
    saved = env.msgs.set_rollback.await_args.args[1]
    assert saved.replaced_by == str(env.new_id)
    last = [f for f in env.frames() if f["type"] == "message_rollback"][-1]
    assert last["rollback"]["state"] == "superseded"
    assert "undo_tool" not in str(last)


async def test_partial_rollback_stops_before_regeneration():
    env = _RbEnv(_reminder(0, "a"), _reminder(1, "b"))
    partial = _record(
        "partial", _entry(1), _entry(0, "failed", code="reminder already fired")
    )
    with _patch_rollback(partial):
        await env.run_with(confirmed=_plan_ids(env))
    env.container.invoke_retry_turn.assert_not_awaited()
    [err] = env.errors()
    assert err["code"] == "retry_partial"
    assert err["rolled_back"] is True
    assert err["rollback"]["state"] == "partial"
    assert "could not undo" in err["detail"]
    assert "message_rollback" in env.frame_types()
    env.container.interface.send_with_thread.assert_not_awaited()


async def test_regeneration_failure_after_full_undo_is_honest():
    env = _RbEnv(_reminder())
    env.container.invoke_retry_turn = AsyncMock(side_effect=RetryFailedError("boom"))
    with _patch_rollback(_record("rolled_back_retry_failed", _entry())):
        await env.run_with(confirmed=_plan_ids(env))
    [err] = env.errors()
    assert err["code"] == "retry_failed"
    assert err["rolled_back"] is True
    assert err["rollback"]["state"] == "rolled_back_retry_failed"
    assert "undid set a reminder" in err["detail"]
    assert "unchanged" not in err["detail"]
    env.container.interface.send_with_thread.assert_not_awaited()
    env.msgs.mark_superseded.assert_not_awaited()


async def test_unexpected_regeneration_error_after_undo_is_honest_too():
    env = _RbEnv(_reminder())
    env.container.invoke_retry_turn = AsyncMock(side_effect=RuntimeError("x"))
    with _patch_rollback(_record("rolled_back_retry_failed", _entry())):
        await env.run_with(confirmed=_plan_ids(env))
    assert env.errors()[0]["rolled_back"] is True
    assert "unchanged" not in env.errors()[0]["detail"]


async def test_pause_at_confirmation_keeps_the_old_reply_and_tracks_the_gate():
    env = _RbEnv(_reminder())
    env.container.invoke_retry_turn = AsyncMock(
        return_value=SimpleNamespace(
            interrupted=True,
            response=None,
            message_id="",
            config={"configurable": {"thread_id": "t1", "retry_replaces": "x"}},
            final_state={},
        )
    )
    gate = ("req-1", {"configurable": {"retry_replaces": "x"}})
    with (
        _patch_rollback(_record("rolled_back_retry_failed", _entry())),
        patch.object(
            turns, "send_confirmation_request", AsyncMock(return_value=gate)
        ) as send,
    ):
        result = await env.run_with(confirmed=_plan_ids(env))
    assert result == gate
    send.assert_awaited_once()
    env.container.interface.send_with_thread.assert_not_awaited()
    env.msgs.mark_superseded.assert_not_awaited()
    assert env.stored_states() == ["rolled_back_awaiting_confirmation"]
    assert env.errors() == []


async def test_text_only_retry_writes_no_rollback_record():
    env = _RbEnv(_call("web_search", access="read"))
    await env.run_with()
    env.msgs.set_rollback.assert_not_awaited()
    assert "message_rollback" not in env.frame_types()
    assert "message_superseded" in env.frame_types()
    assert (
        env.container.interface.send_with_thread.await_args.kwargs["trace"].rollback
        is None
    )


async def test_text_only_retry_after_a_failed_regeneration_supersedes_the_record():
    prior = _record("rolled_back_retry_failed", _entry())
    env = _RbEnv(_reminder(), rollback=prior)
    await env.run_with()  # plan is empty: the only action is already undone
    env.container.invoke_retry_turn.assert_awaited_once()
    assert env.stored_states() == ["superseded"]
    sent = env.container.interface.send_with_thread.await_args.kwargs
    assert sent["trace"].rollback is not None


async def test_text_only_retry_failing_after_a_failed_regeneration_still_says_undone():
    prior = _record("rolled_back_retry_failed", _entry())
    env = _RbEnv(_reminder(), rollback=prior)
    env.container.invoke_retry_turn = AsyncMock(side_effect=RetryFailedError("boom"))
    await env.run_with()
    assert env.errors()[0]["rolled_back"] is True


async def test_undo_failed_record_refuses_retry():
    prior = _record("partial", _entry(0, "failed"))
    env = _RbEnv(_reminder(), rollback=prior)
    await env.run_with()
    assert env.errors()[0]["reason_code"] == "undo_failed"
    env.container.invoke_retry_turn.assert_not_awaited()


# ── the task wrapper's catch-all ─────────────────────────────────────────────


async def test_crash_after_a_completed_rollback_does_not_claim_unchanged():
    mid = uuid4()
    record = _record("rolled_back_retry_failed", _entry())
    msgs = AsyncMock()
    msgs.get_message = AsyncMock(return_value=_msg(id=mid, rollback=record))
    frame = await _retry_crash_frame({"message_id": str(mid)}, msgs)
    assert frame["code"] == "retry_failed"
    assert frame["rolled_back"] is True
    assert "unchanged" not in frame["detail"]
    assert "undid set a reminder" in frame["detail"]
    assert frame["rollback"]["state"] == "rolled_back_retry_failed"


async def test_crash_without_a_rollback_says_unchanged():
    msgs = AsyncMock()
    msgs.get_message = AsyncMock(return_value=_msg())
    frame = await _retry_crash_frame({"message_id": str(uuid4())}, msgs)
    assert "unchanged" in frame["detail"]
    assert "rolled_back" not in frame


async def test_crash_when_the_record_cannot_be_read_does_not_claim_anything():
    msgs = AsyncMock()
    msgs.get_message = AsyncMock(side_effect=RuntimeError("db"))
    frame = await _retry_crash_frame({"message_id": str(uuid4())}, msgs)
    assert "unchanged" not in frame["detail"]
    assert "could not confirm" in frame["detail"]


async def test_run_retry_task_reports_the_stored_rollback_after_an_exception():
    mid = uuid4()
    record = _record("partial", _entry(1), _entry(0, "failed"))
    msgs = AsyncMock()
    msgs.get_message = AsyncMock(return_value=_msg(id=mid, rollback=record))
    conn = SimpleNamespace(send_frame=AsyncMock(), clear_busy=lambda tid: None)
    with patch(
        "ze_api.api.websocket.endpoint.handle_retry",
        AsyncMock(side_effect=RuntimeError("after rollback")),
    ):
        await _run_retry_task(
            {"message_id": str(mid), "thread_id": "t1"},
            object(),
            msgs,
            conn,
            {},
            {},
            "t1",
            object(),
            object(),
        )
    frame = conn.send_frame.await_args.args[0]
    assert frame["code"] == "retry_failed"
    assert frame["rolled_back"] is True
    assert "unchanged" not in frame["detail"]


async def test_run_retry_task_tracks_a_paused_gate():
    pending: dict = {}
    by_thread: dict = {}
    conn = SimpleNamespace(send_frame=AsyncMock(), clear_busy=lambda tid: None)
    gate = ("req-9", {"configurable": {"retry_replaces": str(uuid4())}})
    with patch(
        "ze_api.api.websocket.endpoint.handle_retry", AsyncMock(return_value=gate)
    ):
        await _run_retry_task(
            {"message_id": str(uuid4()), "thread_id": "t1"},
            object(),
            object(),
            conn,
            pending,
            by_thread,
            "t1",
            object(),
            object(),
        )
    assert pending == {"req-9": gate[1]}
    assert by_thread == {"t1": {"req-9"}}
    assert UUID(gate[1]["configurable"]["retry_replaces"])
