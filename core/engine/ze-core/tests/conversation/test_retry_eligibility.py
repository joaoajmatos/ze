"""Retry eligibility is decided on the server from the recorded turn (Phase 165)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from ze_core.conversation.messages.types import (
    Message,
    MessageTrace,
    RollbackEntry,
    RollbackRecord,
    ToolCallTrace,
    WorkspaceUsageTrace,
)
from ze_core.conversation.retry import (
    RetryReason,
    eligibility_payload,
    retry_eligibility,
)


def _msg(role: str = "assistant") -> Message:
    return Message(
        id=uuid4(),
        role=role,  # type: ignore[arg-type]
        text="hi",
        components=[],
        read=True,
        created_at=datetime.now(timezone.utc),
        thread_id="t1",
    )


def _call(
    name: str,
    *,
    access: str = "write",
    reversibility: str | None = None,
    gate: str = "none",
    phrase: str | None = None,
    success: bool = True,
    undo: dict | None = None,
    undo_tool: str | None = None,
    agent: str | None = None,
    call_index: int = 0,
    note: str | None = None,
) -> ToolCallTrace:
    return ToolCallTrace(
        name=name,
        result_snippet="",
        duration_ms=1,
        success=success,
        access=access,
        reversibility=reversibility,
        gate=gate,
        effect_phrase=phrase,
        undo_args=undo,
        undo_tool=undo_tool,
        agent=agent,
        call_index=call_index,
        undo_note=note,
    )


def _rev(name="set_reminder", phrase="set a reminder", **kw) -> ToolCallTrace:
    kw.setdefault("undo", {"reminder_id": "r1"})
    kw.setdefault("undo_tool", "cancel_reminder")
    kw.setdefault("agent", "reminders")
    kw.setdefault("note", "Does not recall a shown notification")
    return _call(name, reversibility="reversible", phrase=phrase, **kw)


def _rollback(*entries: RollbackEntry, state="rolled_back_retry_failed"):
    return RollbackRecord(
        state=state, entries=list(entries), started_at="t", updated_at="t"
    )


def _entry(call_index: int, outcome: str, phrase="set a reminder") -> RollbackEntry:
    return RollbackEntry(
        entry_id=f"e{call_index}",
        call_index=call_index,
        tool="set_reminder",
        undo_tool="cancel_reminder",
        effect_phrase=phrase,
        outcome=outcome,  # type: ignore[arg-type]
    )


def _trace(*calls: ToolCallTrace, known: bool = True, **kw) -> MessageTrace:
    return MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.1,
        is_compound=False,
        subtasks=[],
        tool_calls=list(calls),
        effects_known=known,
        **kw,
    )


def _check(trace, msg=None, **kw):
    msg = msg or _msg()
    kw.setdefault("latest_assistant_id", msg.id)
    return retry_eligibility(msg, trace, **kw)


def test_user_message_gets_no_control() -> None:
    result = _check(_trace(), _msg("user"))
    assert result.applicable is False
    assert result.available is False


def test_text_only_turn_is_available() -> None:
    result = _check(_trace())
    assert result.available is True
    assert result.reason_code is None


def test_read_only_turn_is_available() -> None:
    result = _check(
        _trace(_call("web_search", access="read"), _call("recall", access="read"))
    )
    assert result.available is True


def test_not_latest_blocks() -> None:
    msg = _msg()
    result = retry_eligibility(msg, _trace(), latest_assistant_id=uuid4())
    assert result.reason_code is RetryReason.NOT_LATEST


def test_unknown_latest_blocks() -> None:
    result = retry_eligibility(_msg(), _trace(), latest_assistant_id=None)
    assert result.reason_code is RetryReason.NOT_LATEST


def test_pending_confirmation_wins_over_everything() -> None:
    result = _check(_trace(), pending=True, thread_busy=True)
    assert result.reason_code is RetryReason.TURN_PENDING


def test_busy_thread_blocks() -> None:
    result = _check(_trace(), thread_busy=True)
    assert result.reason_code is RetryReason.BUSY


def test_missing_trace_blocks() -> None:
    result = _check(None)
    assert result.reason_code is RetryReason.TRACE_UNAVAILABLE


def test_old_trace_without_effect_metadata_blocks() -> None:
    result = _check(_trace(_call("web_search", access="unknown"), known=False))
    assert result.reason_code is RetryReason.UNKNOWN_TOOL


def test_old_trace_with_no_tools_still_blocks() -> None:
    result = _check(_trace(known=False))
    assert result.reason_code is RetryReason.UNKNOWN_TOOL


def test_unknown_tool_in_known_trace_blocks() -> None:
    result = _check(_trace(_call("mystery", access="unknown")))
    assert result.reason_code is RetryReason.UNKNOWN_TOOL


@pytest.mark.parametrize(
    ("name", "reversibility", "phrase", "code", "needle"),
    [
        (
            "set_reminder",
            "reversible",
            "set a reminder",
            RetryReason.NOT_UNDOABLE,
            "set a reminder",
        ),
        (
            "create_goal",
            "reversible",
            "created a goal",
            RetryReason.NOT_UNDOABLE,
            "created a goal",
        ),
        (
            "create_workflow",
            "reversible",
            "created a workflow",
            RetryReason.NOT_UNDOABLE,
            "created a workflow",
        ),
        (
            "remember_fact",
            "reversible",
            "saved something to memory",
            RetryReason.NOT_UNDOABLE,
            "saved something to memory",
        ),
        (
            "close_loop",
            "irreversible",
            "closed an open loop",
            RetryReason.HAS_IRREVERSIBLE_ACTION,
            "closed an open loop",
        ),
        (
            "send_email",
            "irreversible",
            "sent an email",
            RetryReason.HAS_IRREVERSIBLE_ACTION,
            "sent an email",
        ),
        (
            "log_outreach_event",
            "irreversible",
            "logged an outreach event",
            RetryReason.HAS_IRREVERSIBLE_ACTION,
            "logged an outreach event",
        ),
        (
            "create_event",
            "irreversible",
            "created a calendar event",
            RetryReason.HAS_IRREVERSIBLE_ACTION,
            "created a calendar event",
        ),
        (
            "ingest_url",
            "irreversible",
            "ingested a web page",
            RetryReason.HAS_IRREVERSIBLE_ACTION,
            "ingested a web page",
        ),
        (
            "legacy_write",
            None,
            None,
            RetryReason.HAS_IRREVERSIBLE_ACTION,
            "ran legacy write",
        ),
    ],
)
def test_action_matrix(name, reversibility, phrase, code, needle) -> None:
    result = _check(_trace(_call(name, reversibility=reversibility, phrase=phrase)))
    assert result.available is False
    assert result.reason_code is code
    assert needle in (result.reason_text or "")
    assert result.reason_text.startswith("This reply ")


def test_reversible_without_payload_says_not_undone_cleanly() -> None:
    result = _check(
        _trace(
            _call("set_reminder", reversibility="reversible", phrase="set a reminder")
        )
    )
    assert result.reason_code is RetryReason.NOT_UNDOABLE
    assert "cannot be undone cleanly" in result.reason_text


def test_irreversible_reason_says_it_cannot_be_undone() -> None:
    result = _check(
        _trace(
            _call("send_email", reversibility="irreversible", phrase="sent an email")
        )
    )
    assert "cannot be undone" in result.reason_text


def test_mixed_reversibility_is_irreversible() -> None:
    result = _check(
        _trace(
            _rev(call_index=0),
            _call(
                "send_email",
                reversibility="irreversible",
                phrase="sent an email",
                call_index=1,
            ),
        )
    )
    assert result.reason_code is RetryReason.HAS_IRREVERSIBLE_ACTION
    assert "set a reminder and sent an email" in result.reason_text
    assert result.plan == []


def test_action_names_are_capped_at_three() -> None:
    calls = [
        _call(f"t{i}", reversibility="irreversible", phrase=f"did thing {i}")
        for i in range(5)
    ]
    result = _check(_trace(*calls))
    assert len(result.actions) == 3
    assert "did thing 3" not in result.reason_text


def test_failed_reversible_write_without_payload_is_not_undoable() -> None:
    result = _check(
        _trace(
            _call(
                "set_reminder",
                reversibility="reversible",
                phrase="set a reminder",
                success=False,
            )
        )
    )
    assert result.reason_code is RetryReason.NOT_UNDOABLE


def test_failed_write_still_counts() -> None:
    result = _check(
        _trace(_call("send_email", reversibility="irreversible", success=False))
    )
    assert result.reason_code is RetryReason.HAS_IRREVERSIBLE_ACTION


def test_approved_gate_is_confirmed_action() -> None:
    result = _check(
        _trace(
            _call(
                "send_email",
                reversibility="irreversible",
                gate="approved",
                phrase="sent an email",
            )
        )
    )
    assert result.reason_code is RetryReason.CONFIRMED_ACTION


@pytest.mark.parametrize("gate", ["denied", "expired"])
def test_denied_or_expired_gate_is_not_an_action(gate) -> None:
    result = _check(
        _trace(
            _call("send_email", reversibility="irreversible", gate=gate, success=False)
        )
    )
    assert result.available is True


def test_workspace_run_blocks() -> None:
    result = _check(
        _trace(
            _call(
                "workspace_run",
                reversibility="irreversible",
                phrase="ran a workspace command",
            ),
            workspace=WorkspaceUsageTrace(runs=[{"command": "ls", "success": True}]),
        )
    )
    assert result.reason_code is RetryReason.WORKSPACE_RUN


def test_in_progress_workspace_run_blocks() -> None:
    result = _check(
        _trace(
            workspace=WorkspaceUsageTrace(
                runs=[{"command": "make", "status": "in_progress"}]
            )
        )
    )
    assert result.reason_code is RetryReason.WORKSPACE_RUN


def test_workspace_read_only_is_available() -> None:
    result = _check(
        _trace(
            _call("workspace_read", access="read"),
            workspace=WorkspaceUsageTrace(files=[{"path": "a", "op": "read"}]),
        )
    )
    assert result.available is True


def test_delegate_wrapper_alone_is_not_an_action() -> None:
    result = _check(_trace(_call("delegate_to_agent", access="delegate")))
    assert result.available is True


def test_delegate_with_nested_send_is_irreversible() -> None:
    result = _check(
        _trace(
            _call("delegate_to_agent", access="delegate"),
            _call("send_email", reversibility="irreversible", phrase="sent an email"),
        )
    )
    assert result.reason_code is RetryReason.HAS_IRREVERSIBLE_ACTION


def test_available_result_has_no_reason() -> None:
    result = _check(_trace())
    assert result.reason_text is None
    assert result.actions == []


@pytest.mark.parametrize("gate", ["denied", "expired"])
def test_denied_workspace_run_does_not_block(gate) -> None:
    result = _check(
        _trace(
            _call(
                "workspace_run", reversibility="irreversible", gate=gate, success=False
            ),
            workspace=WorkspaceUsageTrace(runs=[{"command": "ls", "success": False}]),
        )
    )
    assert result.available is True


def test_reminder_only_reply_is_available_with_one_entry_plan() -> None:
    msg = _msg()
    result = _check(_trace(_rev()), msg)
    assert result.available is True
    assert result.reason_code is None
    [entry] = result.plan
    assert entry.tool == "set_reminder"
    assert entry.undo_tool == "cancel_reminder"
    assert entry.agent == "reminders"
    assert entry.undo_args == {"reminder_id": "r1"}
    assert entry.effect_phrase == "set a reminder"
    assert entry.undo_note == "Does not recall a shown notification"


def test_plan_is_in_reverse_call_order() -> None:
    result = _check(
        _trace(
            _rev(call_index=0),
            _rev("create_goal", "created a goal", call_index=2, undo={"goal_id": "g"}),
            _rev(call_index=5, undo={"reminder_id": "r2"}),
        )
    )
    assert [e.call_index for e in result.plan] == [5, 2, 0]


def test_reinforced_loop_without_payload_is_not_undoable() -> None:
    result = _check(
        _trace(
            _rev(),
            _call(
                "track_loop",
                reversibility="reversible",
                phrase="started tracking a concern",
                call_index=1,
            ),
        )
    )
    assert result.reason_code is RetryReason.NOT_UNDOABLE
    assert result.plan == []


def test_approved_reversible_action_with_payload_is_available() -> None:
    result = _check(_trace(_rev(gate="approved")))
    assert result.available is True
    assert len(result.plan) == 1


def test_approved_irreversible_action_is_confirmed_action() -> None:
    result = _check(
        _trace(
            _rev(call_index=0),
            _call(
                "send_email",
                reversibility="irreversible",
                gate="approved",
                phrase="sent an email",
                call_index=1,
            ),
        )
    )
    assert result.reason_code is RetryReason.CONFIRMED_ACTION


def test_reversible_with_payload_but_no_agent_is_not_undoable() -> None:
    result = _check(_trace(_rev(agent=None)))
    assert result.reason_code is RetryReason.NOT_UNDOABLE


def test_reversible_with_payload_but_no_undo_tool_is_not_undoable() -> None:
    result = _check(_trace(_rev(undo_tool=None)))
    assert result.reason_code is RetryReason.NOT_UNDOABLE


def test_unknown_tool_still_wins_over_plan() -> None:
    result = _check(_trace(_rev(), _call("mystery", access="unknown", call_index=1)))
    assert result.reason_code is RetryReason.UNKNOWN_TOOL


def test_denied_reversible_gate_is_not_an_action() -> None:
    result = _check(_trace(_rev(gate="denied", undo=None, success=False)))
    assert result.available is True
    assert result.plan == []


def test_workspace_run_beats_a_reversible_plan() -> None:
    result = _check(
        _trace(
            _rev(call_index=0),
            _call("workspace_run", reversibility="irreversible", call_index=1),
            workspace=WorkspaceUsageTrace(runs=[{"command": "ls", "success": True}]),
        )
    )
    assert result.reason_code is RetryReason.WORKSPACE_RUN


def test_rollback_record_with_failed_entry_is_undo_failed() -> None:
    record = _rollback(
        _entry(0, "undone", "created a goal"),
        _entry(1, "failed"),
        state="partial",
    )
    result = _check(_trace(_rev(call_index=1), _rev(call_index=0)), rollback=record)
    assert result.available is False
    assert result.reason_code is RetryReason.UNDO_FAILED
    assert "set a reminder" in result.reason_text
    assert "created a goal" in result.reason_text


def test_undone_entries_drop_out_of_the_plan() -> None:
    record = _rollback(_entry(2, "undone"))
    result = _check(
        _trace(
            _rev(call_index=0, undo={"reminder_id": "a"}),
            _rev(call_index=2, undo={"reminder_id": "b"}),
        ),
        rollback=record,
    )
    assert result.available is True
    assert [e.call_index for e in result.plan] == [0]


def test_all_undone_is_available_text_only() -> None:
    record = _rollback(_entry(0, "undone"))
    result = _check(_trace(_rev()), rollback=record)
    assert result.available is True
    assert result.plan == []


def test_undone_reminder_beside_irreversible_still_blocks() -> None:
    record = _rollback(_entry(0, "undone"))
    result = _check(
        _trace(
            _rev(call_index=0),
            _call(
                "send_email",
                reversibility="irreversible",
                phrase="sent an email",
                call_index=1,
            ),
        ),
        rollback=record,
    )
    assert result.reason_code is RetryReason.HAS_IRREVERSIBLE_ACTION


def test_entry_ids_are_stable_and_change_with_the_payload() -> None:
    msg = _msg()
    trace = _trace(_rev())
    first = _check(trace, msg).plan[0].entry_id
    assert _check(trace, msg).plan[0].entry_id == first
    assert len(first) == 16
    other = _check(_trace(_rev(undo={"reminder_id": "r2"})), msg).plan[0].entry_id
    assert other != first
    assert _check(trace, _msg()).plan[0].entry_id != first


def test_entry_id_ignores_payload_key_order() -> None:
    msg = _msg()
    a = _check(_trace(_rev(undo={"a": 1, "b": 2})), msg).plan[0].entry_id
    b = _check(_trace(_rev(undo={"b": 2, "a": 1})), msg).plan[0].entry_id
    assert a == b


def test_payload_exposes_plan_without_agent_or_undo_args() -> None:
    payload = eligibility_payload(_check(_trace(_rev())))
    [entry] = payload["plan"]
    assert set(entry) == {"entry_id", "tool", "effect_phrase", "undo_note"}
    assert payload["available"] is True


def test_removed_reason_codes_are_gone() -> None:
    values = {r.value for r in RetryReason}
    assert "has_reversible_action" not in values
    assert "has_write_action" not in values
    assert {"not_undoable", "undo_failed"} <= values
