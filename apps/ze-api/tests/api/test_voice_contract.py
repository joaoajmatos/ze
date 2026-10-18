"""Contract for the voice route, the voice context and the trace `input`."""

import pytest
from pydantic import ValidationError

from ze_api.api.v0.messages.router import _trace_to_response
from ze_api.api.v0.messages.schemas import MessageTraceResponse
from ze_api.api.ws.schemas import WsScreenContext, WsTraceUpdateFrame
from ze_api.cli.openapi_export import export_openapi
from ze_core.conversation.messages.types import InputTrace, MessageTrace


def test_openapi_lists_transcribe_voice():
    schema = export_openapi()
    op = schema["paths"]["/api/v0/voice/transcriptions"]["post"]
    assert op["operationId"] == "transcribeVoice"
    assert "TranscriptionResponse" in str(op["responses"]["200"])


def test_ws_screen_context_accepts_voice_reference():
    ctx = WsScreenContext.model_validate({"voice": {"transcription_id": "a" * 32}})
    assert ctx.voice is not None
    assert ctx.voice.transcription_id == "a" * 32


def test_ws_screen_context_rejects_long_voice_reference():
    with pytest.raises(ValidationError):
        WsScreenContext.model_validate({"voice": {"transcription_id": "a" * 65}})


def test_trace_schemas_carry_input():
    assert "input" in MessageTraceResponse.model_json_schema()["properties"]
    assert "input" in WsTraceUpdateFrame.model_json_schema()["properties"]


def test_trace_response_carries_voice_input():
    trace = MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.1,
        is_compound=False,
        subtasks=[],
        input=InputTrace(modality="voice", duration_s=3.4, edited=True),
    )
    response = _trace_to_response(trace)
    assert response.input is not None
    assert (response.input.modality, response.input.duration_s, response.input.edited) == ("voice", 3.4, True)


def test_trace_response_text_turn_has_no_input():
    trace = MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.1,
        is_compound=False,
        subtasks=[],
    )
    assert _trace_to_response(trace).input is None
