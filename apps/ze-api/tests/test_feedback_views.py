"""Feedback view carries the undo plan and the stored rollback record (Phase 180 T026)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ze_api.api.v0.messages.views import ThreadState, build_view
from ze_core.conversation.messages.types import (
    Message,
    MessageTrace,
    RollbackEntry,
    RollbackRecord,
    ToolCallTrace,
)


def _msg(rollback=None) -> Message:
    return Message(
        id=uuid4(),
        role="assistant",
        text="done",
        components=[],
        read=True,
        created_at=datetime.now(timezone.utc),
        thread_id="t1",
        rollback=rollback,
    )


def _reminder_trace(**kw) -> MessageTrace:
    call = ToolCallTrace(
        name="set_reminder",
        result_snippet="",
        duration_ms=1,
        success=True,
        access="write",
        reversibility="reversible",
        undo_tool="cancel_reminder",
        effect_phrase="set a reminder",
        agent="reminders",
        undo_args={"reminder_id": "secret-id"},
        undo_note="Does not recall a notification already shown",
        call_index=0,
    )
    return MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.1,
        is_compound=False,
        subtasks=[],
        tool_calls=[call],
        effects_known=True,
        **kw,
    )


def _state(msg) -> ThreadState:
    return ThreadState(latest_assistant_id=msg.id, busy=False, pending=False)


def test_plan_is_public_and_hides_agent_and_undo_args():
    msg = _msg()
    view = build_view(msg, [], _reminder_trace(), _state(msg))
    assert view.retry.available is True
    [entry] = view.retry.plan
    dumped = entry.model_dump()
    assert dumped["tool"] == "set_reminder"
    assert dumped["effect_phrase"] == "set a reminder"
    assert dumped["undo_note"] == "Does not recall a notification already shown"
    assert set(dumped) == {"entry_id", "tool", "effect_phrase", "undo_note"}
    assert "secret-id" not in view.model_dump_json()


def test_text_only_reply_has_empty_plan_and_no_rollback():
    msg = _msg()
    trace = _reminder_trace()
    trace.tool_calls = []
    view = build_view(msg, [], trace, _state(msg))
    assert view.retry.available is True
    assert view.retry.plan == []
    assert view.rollback is None


def test_rollback_record_is_passed_into_eligibility_and_view():
    entry = RollbackEntry(
        entry_id="x",
        call_index=0,
        tool="set_reminder",
        undo_tool="cancel_reminder",
        effect_phrase="set a reminder",
        outcome="undone",
        at="t",
    )
    record = RollbackRecord(
        state="rolled_back_retry_failed",
        entries=[entry],
        started_at="t",
        updated_at="t",
    )
    msg = _msg(rollback=record)
    view = build_view(msg, [], _reminder_trace(), _state(msg))
    assert view.rollback is not None
    assert view.rollback.state == "rolled_back_retry_failed"
    assert view.rollback.entries[0].outcome == "undone"
    # the undone call dropped out, so the retry is text-only
    assert view.retry.available is True
    assert view.retry.plan == []


def test_failed_undo_makes_retry_unavailable():
    entry = RollbackEntry(
        entry_id="x",
        call_index=0,
        tool="set_reminder",
        undo_tool="cancel_reminder",
        effect_phrase="set a reminder",
        outcome="failed",
        at="t",
        failure_code="boom",
    )
    record = RollbackRecord(
        state="partial", entries=[entry], started_at="t", updated_at="t"
    )
    msg = _msg(rollback=record)
    view = build_view(msg, [], _reminder_trace(), _state(msg))
    assert view.retry.available is False
    assert view.retry.reason_code == "undo_failed"
    assert view.rollback.state == "partial"
