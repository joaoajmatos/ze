"""Write confirmation outcomes on live and stored message traces (phase 181)."""

from ze_api.api.v0.messages.schemas import (
    MessageTraceResponse,
    WriteConfirmationOutcomeResponse,
)
from ze_api.api.ws.schemas import WsTraceUpdateFrame


def test_live_trace_update_carries_write_confirmations():
    props = WsTraceUpdateFrame.model_json_schema()["properties"]
    assert "write_confirmations" in props
    assert (
        "write_confirmations" in MessageTraceResponse.model_json_schema()["properties"]
    )


def test_outcome_accepts_pre_approved():
    row = WriteConfirmationOutcomeResponse(
        request_id="r1",
        round=1,
        item_id="i1",
        agent="messenger",
        tool="send_email",
        outcome="pre_approved",
    )
    assert row.outcome == "pre_approved"
