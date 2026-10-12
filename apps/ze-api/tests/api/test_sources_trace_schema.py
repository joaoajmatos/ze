"""REST / WS: web sources on message traces."""

from types import SimpleNamespace

from ze_api.api.messages import _trace_to_response
from ze_api.api.schemas import MessageTraceResponse, WsTraceUpdateFrame
from ze_core.conversation.messages.types import MessageTrace, SourceTrace


def test_trace_schemas_include_sources():
    assert "sources" in MessageTraceResponse.model_json_schema()["properties"]
    assert "sources" in WsTraceUpdateFrame.model_json_schema()["properties"]


def test_trace_response_carries_sources():
    trace = MessageTrace(
        agent="research",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.1,
        is_compound=False,
        subtasks=["research"],
        sources=[SourceTrace(url="https://a.test", title="A")],
    )
    response = _trace_to_response(trace)
    assert [(s.url, s.title) for s in response.sources] == [("https://a.test", "A")]


def test_trace_response_without_sources_is_empty():
    trace = SimpleNamespace(
        agent="x",
        routing_method="embedding",
        confidence=1.0,
        score_gap=0.0,
        is_compound=False,
        subtasks=[],
        memory_chunks=[],
        tool_calls=[],
        total_duration_ms=0,
    )
    assert _trace_to_response(trace).sources == []
