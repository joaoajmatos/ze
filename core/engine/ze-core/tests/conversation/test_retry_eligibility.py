"""Retry eligibility is decided on the server from the recorded turn (Phase 165)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from ze_core.conversation.messages.types import (
    Message,
    MessageTrace,
    ToolCallTrace,
    WorkspaceUsageTrace,
)
from ze_core.conversation.retry import RetryReason, retry_eligibility


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
            RetryReason.HAS_REVERSIBLE_ACTION,
            "set a reminder",
        ),
        (
            "create_goal",
            "reversible",
            "created a goal",
            RetryReason.HAS_REVERSIBLE_ACTION,
            "created a goal",
        ),
        (
            "create_workflow",
            "reversible",
            "created a workflow",
            RetryReason.HAS_REVERSIBLE_ACTION,
            "created a workflow",
        ),
        (
            "remember_fact",
            "reversible",
            "saved something to memory",
            RetryReason.HAS_REVERSIBLE_ACTION,
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
        ("legacy_write", None, None, RetryReason.HAS_WRITE_ACTION, "ran legacy write"),
    ],
)
def test_action_matrix(name, reversibility, phrase, code, needle) -> None:
    result = _check(_trace(_call(name, reversibility=reversibility, phrase=phrase)))
    assert result.available is False
    assert result.reason_code is code
    assert needle in (result.reason_text or "")
    assert result.reason_text.startswith("This reply ")


def test_reversible_reason_says_undo_is_separate() -> None:
    result = _check(
        _trace(
            _call("set_reminder", reversibility="reversible", phrase="set a reminder")
        )
    )
    assert "undone separately" in result.reason_text


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
            _call("set_reminder", reversibility="reversible", phrase="set a reminder"),
            _call("send_email", reversibility="irreversible", phrase="sent an email"),
        )
    )
    assert result.reason_code is RetryReason.HAS_IRREVERSIBLE_ACTION
    assert "set a reminder and sent an email" in result.reason_text


def test_action_names_are_capped_at_three() -> None:
    calls = [
        _call(f"t{i}", reversibility="irreversible", phrase=f"did thing {i}")
        for i in range(5)
    ]
    result = _check(_trace(*calls))
    assert len(result.actions) == 3
    assert "did thing 3" not in result.reason_text


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
