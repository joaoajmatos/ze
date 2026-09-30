"""OpenAPI / REST: judgments field on message traces (phase 162 US3)."""

from ze_api.api.schemas import MessageTraceResponse, WsTraceUpdateFrame


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
