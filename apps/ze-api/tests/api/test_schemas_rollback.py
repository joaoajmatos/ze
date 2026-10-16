"""Schemas for Phase 180 retry rollback."""

from types import SimpleNamespace
from uuid import uuid4

from ze_api.api.v0.messages.router import _trace_to_response
from ze_api.api.shared_schemas import RollbackRecordResponse
from ze_api.api.v0.messages.schemas import (
    FeedbackView,
    MessageSchema,
    MessageTraceResponse,
    RetryEligibilityResponse,
)
from ze_api.api.ws.schemas import (
    WsErrorFrame,
    WsInboundFrame,
    WsMessageRollbackFrame,
    WsRetryFrame,
    WsTraceUpdateFrame,
)
from pydantic import TypeAdapter
from ze_core.conversation.messages.types import (
    Message,
    RollbackEntry,
    RollbackRecord,
    RollbackTrace,
)

_ENTRY = {
    "entry_id": "9f2c1a0b7d3e4f51",
    "tool": "set_reminder",
    "effect_phrase": "set a reminder",
    "outcome": "undone",
    "at": "2026-10-13T10:00:00+00:00",
    "failure_code": None,
}
_RECORD = {"state": "partial", "entries": [_ENTRY], "replaced_by": None}


def test_retry_frame_confirmed_plan_optional():
    assert (
        WsRetryFrame(type="retry", message_id="m", thread_id="t").confirmed_plan is None
    )
    frame = WsRetryFrame(
        type="retry", message_id="m", thread_id="t", confirmed_plan=["a"]
    )
    assert frame.confirmed_plan == ["a"]


def test_eligibility_plan_defaults_empty_and_maps_entries():
    assert RetryEligibilityResponse(available=True).plan == []
    r = RetryEligibilityResponse(
        available=True,
        plan=[
            {
                "entry_id": "e1",
                "tool": "set_reminder",
                "effect_phrase": "set a reminder",
                "undo_note": "note",
            }
        ],
    )
    assert r.plan[0].undo_note == "note"


def test_feedback_view_rollback_defaults_none():
    view = FeedbackView(
        message_id=uuid4(),
        retry=RetryEligibilityResponse(available=True),
        trace_present=True,
    )
    assert view.rollback is None


def test_rollback_record_response_fields():
    rec = RollbackRecordResponse.model_validate(_RECORD)
    assert rec.state == "partial"
    assert rec.entries[0].outcome == "undone"
    assert rec.replaced_by is None


def test_message_schema_maps_rollback_from_dataclass():
    msg = Message(
        id=uuid4(),
        role="assistant",
        text="hi",
        components=[],
        read=True,
        thread_id="t",
        created_at=__import__("datetime").datetime.now(),
        rollback=RollbackRecord(
            state="partial",
            entries=[
                RollbackEntry(
                    entry_id="e1",
                    call_index=0,
                    tool="set_reminder",
                    undo_tool="cancel_reminder",
                    effect_phrase="set a reminder",
                    outcome="undone",
                )
            ],
            started_at="2026-10-13T10:00:00+00:00",
            updated_at="2026-10-13T10:00:00+00:00",
        ),
    )
    out = MessageSchema.model_validate(msg.__dict__)
    assert out.rollback is not None
    assert out.rollback.entries[0].tool == "set_reminder"
    dumped = out.rollback.model_dump()
    assert "undo_tool" not in dumped["entries"][0]
    assert "call_index" not in dumped["entries"][0]


def test_message_schema_rollback_default_none():
    assert "rollback" in MessageSchema.model_json_schema()["properties"]


def test_error_frame_new_codes_and_fields():
    frame = WsErrorFrame(
        type="error",
        detail="d",
        code="retry_partial",
        rolled_back=True,
        rollback=_RECORD,
        plan=[
            {
                "entry_id": "e",
                "tool": "t",
                "effect_phrase": "p",
                "undo_note": None,
            }
        ],
    )
    assert frame.rolled_back is True
    assert frame.rollback.state == "partial"
    assert frame.plan[0].entry_id == "e"
    assert WsErrorFrame(type="error", detail="d").rolled_back is None


def test_message_rollback_frame_in_inbound_union():
    frame = TypeAdapter(WsInboundFrame).validate_python(
        {
            "type": "message_rollback",
            "message_id": "m",
            "thread_id": "t",
            "rollback": _RECORD,
        }
    )
    assert isinstance(frame, WsMessageRollbackFrame)


def test_trace_response_maps_rollback():
    trace = SimpleNamespace(
        agent="companion",
        routing_method="embedding",
        confidence=0.8,
        score_gap=0.1,
        is_compound=False,
        subtasks=[],
        memory_chunks=[],
        tool_calls=[],
        total_duration_ms=0,
        rollback=RollbackTrace(
            replaces="m1",
            entries=[
                RollbackEntry(
                    entry_id="e1",
                    call_index=0,
                    tool="set_reminder",
                    undo_tool="cancel_reminder",
                    effect_phrase="set a reminder",
                    outcome="undone",
                )
            ],
        ),
    )
    resp = _trace_to_response(trace)
    assert resp.rollback.replaces == "m1"
    assert resp.rollback.entries[0].effect_phrase == "set a reminder"
    assert MessageTraceResponse.model_fields["rollback"].default is None


def test_trace_update_frame_carries_rollback():
    assert "rollback" in WsTraceUpdateFrame.model_json_schema()["properties"]
