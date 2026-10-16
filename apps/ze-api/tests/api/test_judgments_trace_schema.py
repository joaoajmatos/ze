"""OpenAPI / REST: judgments field on message traces (phase 162 US3)."""

import pytest
from pydantic import ValidationError

from ze_api.api.schemas import (
    MessageTraceEntry,
    MessageTraceResponse,
    TierTraceResponse,
    WsTraceUpdateFrame,
)


def test_ws_trace_update_schema_includes_tier():
    props = WsTraceUpdateFrame.model_json_schema()["properties"]
    assert "tier" in props


def test_message_trace_schema_includes_tier_and_the_entry_does_not_repeat_it():
    assert "tier" in MessageTraceResponse.model_json_schema()["properties"]
    assert "tier" not in MessageTraceEntry.model_json_schema()["properties"]


def test_tier_trace_response_rejects_an_unknown_tier():
    with pytest.raises(ValidationError):
        TierTraceResponse(agent="a", tier="medium", decided_by="x", model="m")


def test_message_trace_schema_includes_judgments():
    props = MessageTraceResponse.model_json_schema()["properties"]
    assert "judgments" in props


def test_ws_trace_update_schema_includes_judgments():
    props = WsTraceUpdateFrame.model_json_schema()["properties"]
    assert "judgments" in props


def test_judgments_default_empty():
    trace = MessageTraceResponse(
        agent="companion",
        routing_method="embedding",
        confidence=0.8,
        score_gap=0.1,
        is_compound=False,
        subtasks=[],
        memory_chunks=[],
        tool_calls=[],
        total_duration_ms=0,
    )
    assert trace.judgments == []


def test_message_trace_schema_includes_loop_offer_ids():
    props = MessageTraceResponse.model_json_schema()["properties"]
    assert "loop_offer_ids" in props
