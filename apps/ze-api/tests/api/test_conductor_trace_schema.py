"""OpenAPI / REST: conductor fields on message traces (phase 154)."""

from ze_api.api.schemas import MessageTraceResponse, WsTraceUpdateFrame


def test_message_trace_schema_includes_conductor_fields():
    props = MessageTraceResponse.model_json_schema()["properties"]
    assert "conductor_hint" in props
    assert "conductor_ledger" in props
    ledger = props["conductor_ledger"]
    assert "items" in ledger or "$ref" in str(ledger)


def test_ws_trace_update_schema_includes_conductor_fields():
    props = WsTraceUpdateFrame.model_json_schema()["properties"]
    assert "conductor_hint" in props
    assert "conductor_ledger" in props
