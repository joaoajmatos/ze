from __future__ import annotations

from dataclasses import asdict

from ze_core.conversation.messages.store import _parse_trace
from ze_core.conversation.messages.types import (
    MessageTrace,
    RollbackEntry,
    RollbackRecord,
    RollbackTrace,
    ToolCallTrace,
)


def _entry(**kw) -> RollbackEntry:
    base = dict(
        entry_id="abc",
        call_index=0,
        tool="set_reminder",
        undo_tool="cancel_reminder",
        effect_phrase="set a reminder",
        outcome="undone",
        at="2026-10-13T10:00:00+00:00",
    )
    base.update(kw)
    return RollbackEntry(**base)


def test_record_round_trips_through_dict():
    record = RollbackRecord(
        state="partial",
        entries=[_entry(), _entry(outcome="failed", failure_code="Boom", call_index=1)],
        started_at="2026-10-13T10:00:00+00:00",
        updated_at="2026-10-13T10:00:01+00:00",
    )
    assert RollbackRecord.from_dict(asdict(record)) == record


def test_record_from_dict_tolerates_unknown_keys_and_missing_optionals():
    data = {
        "state": "superseded",
        "entries": [{**asdict(_entry()), "extra": 1}],
        "started_at": "t",
        "updated_at": "t",
        "future_field": True,
    }
    record = RollbackRecord.from_dict(data)
    assert record.replaced_by is None
    assert record.entries[0].failure_code is None


def test_old_trace_rows_parse_with_empty_new_fields():
    trace = _parse_trace(
        {
            "agent": "companion",
            "routing_method": "embedding",
            "confidence": 0.9,
            "score_gap": 0.1,
            "is_compound": False,
            "tool_calls": [
                {
                    "name": "set_reminder",
                    "result_snippet": "",
                    "duration_ms": 1,
                    "success": True,
                }
            ],
        }
    )
    call = trace.tool_calls[0]
    assert call.agent is None and call.undo_args is None and call.undo_note is None
    assert trace.rollback is None


def test_trace_with_rollback_round_trips():
    trace = MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.1,
        is_compound=False,
        subtasks=[],
        tool_calls=[
            ToolCallTrace(
                name="set_reminder",
                result_snippet="",
                duration_ms=1,
                success=True,
                agent="reminders",
                undo_args={"reminder_id": "r1"},
                undo_note="n",
                call_index=2,
            )
        ],
        rollback=RollbackTrace(replaces="old-id", entries=[_entry()]),
    )
    parsed = _parse_trace(asdict(trace))
    assert parsed == trace
