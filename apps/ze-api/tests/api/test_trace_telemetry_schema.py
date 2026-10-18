"""187b: the trace contract carries stages, usage, scores, bars and tool ids."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.deps import get_message_store, require_api_key
from ze_api.api.v0.messages.router import router
from ze_api.api.v0.messages.schemas import MessageTraceResponse
from ze_api.api.ws.schemas import WsTraceUpdateFrame
from ze_api.interface.native import NativeAppInterface
from ze_core.conversation.messages.types import (
    JudgmentBar,
    JudgmentTrace,
    MessageTrace,
    ModelUsage,
    RoutingScore,
    RoutingThresholds,
    StageTiming,
    ToolCallTrace,
    TurnUsage,
)

NEW_FIELDS = {
    "tool_duration_ms",
    "turn_duration_ms",
    "paused_ms",
    "stages",
    "usage",
    "routing_scores",
    "routing_thresholds",
    "telemetry_partial",
}


def _full_trace() -> MessageTrace:
    return MessageTrace(
        agent="calendar",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.2,
        is_compound=False,
        subtasks=["calendar"],
        tool_calls=[
            ToolCallTrace(
                name="list_events",
                result_snippet="ok",
                duration_ms=312,
                success=True,
                call_id="9f",
                start_offset_ms=640,
            )
        ],
        judgments=[
            JudgmentTrace(
                question_id="agent",
                kind="choice",
                latency_ms=4,
                surface="routing",
                bar=JudgmentBar("choice_trust", 0.5),
            )
        ],
        tool_duration_ms=312,
        turn_duration_ms=2140,
        paused_ms=20000,
        stages=[StageTiming("fetch_context", 212, 88, 1)],
        usage=TurnUsage(
            main_model="m",
            models=[ModelUsage("m", 2, 9120, 410, 5200, 0.0335, False)],
            context_fill=0.026,
            context_window=200000,
            system_one_tokens=1840,
        ),
        routing_scores=[RoutingScore("calendar", 0.83)],
        routing_thresholds=RoutingThresholds(0.78, 0.05),
        telemetry_partial=True,
    )


def _app(store: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[require_api_key] = lambda: None
    app.dependency_overrides[get_message_store] = lambda: store
    app.include_router(router, prefix="/api/v0")
    return app


@pytest.mark.asyncio
async def test_rest_trace_carries_every_new_field():
    store = AsyncMock()
    store.get_trace = AsyncMock(return_value=_full_trace())
    async with AsyncClient(
        transport=ASGITransport(app=_app(store)), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/messages/{uuid4()}/trace",
            headers={"Authorization": "Bearer k"},
        )
    body = resp.json()
    assert "total_duration_ms" not in body
    assert body["tool_duration_ms"] == 312
    assert body["turn_duration_ms"] == 2140 and body["paused_ms"] == 20000
    assert body["stages"] == [
        {"name": "fetch_context", "start_ms": 212, "duration_ms": 88, "run": 1}
    ]
    assert body["usage"]["models"][0]["max_prompt_tokens"] == 5200
    assert body["usage"]["system_one_tokens"] == 1840
    assert body["routing_scores"] == [{"agent": "calendar", "score": 0.83}]
    assert body["routing_thresholds"] == {"threshold": 0.78, "gap": 0.05}
    assert body["telemetry_partial"] is True
    assert body["tool_calls"][0]["call_id"] == "9f"
    assert body["tool_calls"][0]["start_offset_ms"] == 640
    judgment = body["judgments"][0]
    assert judgment["surface"] == "routing"
    assert judgment["bar"] == {"name": "choice_trust", "value": 0.5}


@pytest.mark.asyncio
async def test_rest_trace_without_telemetry_serializes_nulls():
    trace = MessageTrace(
        agent="a",
        routing_method="embedding",
        confidence=1.0,
        score_gap=0.0,
        is_compound=False,
        subtasks=[],
        judgments=[JudgmentTrace(question_id="q", kind="noul", latency_ms=1)],
    )
    store = AsyncMock()
    store.get_trace = AsyncMock(return_value=trace)
    async with AsyncClient(
        transport=ASGITransport(app=_app(store)), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/messages/{uuid4()}/trace",
            headers={"Authorization": "Bearer k"},
        )
    body = resp.json()
    assert body["turn_duration_ms"] is None and body["usage"] is None
    assert body["stages"] == [] and body["routing_scores"] == []
    assert body["routing_thresholds"] is None and body["paused_ms"] == 0
    assert body["judgments"][0]["surface"] is None
    assert body["judgments"][0]["bar"] is None


def test_schemas_name_the_new_fields_and_drop_the_old():
    for schema in (MessageTraceResponse, WsTraceUpdateFrame):
        props = schema.model_json_schema()["properties"]
        assert NEW_FIELDS <= set(props)
        assert "total_duration_ms" not in props


@pytest.mark.asyncio
async def test_trace_partial_base_frame_has_zero_tool_duration():
    conn = AsyncMock()
    interface = NativeAppInterface.__new__(NativeAppInterface)
    interface._conn = conn
    await interface.send_trace_partial(
        "m1", {"stages": [{"name": "x", "start_ms": 0, "duration_ms": 1, "run": 1}]}, "t1"
    )
    frame = conn.send_frame.call_args.args[0]
    assert frame["tool_duration_ms"] == 0 and "total_duration_ms" not in frame
    assert frame["stages"][0]["name"] == "x"
