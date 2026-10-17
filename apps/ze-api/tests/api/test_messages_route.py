"""Tests for GET /api/v0/messages/traces batch endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.deps import get_message_store, require_api_key
from ze_api.api.v0.messages.router import router
from ze_core.conversation.messages.types import (
    MemoryChunkTrace,
    MessageTrace,
    SkillUsageTrace,
    TierTrace,
    ToolCallTrace,
)

API_KEY = "test-key"


def _trace(skills_used: list[SkillUsageTrace] | None = None) -> MessageTrace:
    return MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.2,
        is_compound=False,
        subtasks=[],
        memory_chunks=[MemoryChunkTrace(text="fact", score=0.8, source="memory_facts")],
        tool_calls=[
            ToolCallTrace(
                name="search", result_snippet="ok", duration_ms=10, success=True
            )
        ],
        total_duration_ms=100,
        skills_used=skills_used or [],
    )


def _make_app(store: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[require_api_key] = lambda: None
    app.dependency_overrides[get_message_store] = lambda: store
    app.include_router(router, prefix="/api/v0")
    return app


@pytest.mark.asyncio
async def test_get_message_traces_returns_batch():
    id1, id2 = uuid4(), uuid4()
    store = AsyncMock()
    store.get_traces = AsyncMock(return_value={id1: _trace()})

    app = _make_app(store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/messages/traces",
            params={"ids": [str(id1), str(id2)]},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["traces"]) == 1
    assert data["traces"][0]["message_id"] == str(id1)
    assert data["traces"][0]["trace"]["agent"] == "companion"
    store.get_traces.assert_awaited_once()
    called_ids = store.get_traces.call_args.args[0]
    assert set(called_ids) == {id1, id2}


@pytest.mark.asyncio
async def test_get_message_traces_empty_ids():
    store = AsyncMock()
    store.get_traces = AsyncMock()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/messages/traces",
            params={"ids": []},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json()["traces"] == []
    store.get_traces.assert_not_called()


# ── GET /messages/{id}/trace — skills_used (Phase 114, User Story 2) ────────────


@pytest.mark.asyncio
async def test_get_message_trace_includes_skills_used():
    message_id = uuid4()
    skill_usage = SkillUsageTrace(
        skill_id="skill-1",
        name="Pirate Speak",
        source="imported",
        trigger="automatic",
        similarity=0.82,
    )
    store = AsyncMock()
    store.get_trace = AsyncMock(return_value=_trace(skills_used=[skill_usage]))

    app = _make_app(store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/messages/{message_id}/trace",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["skills_used"] == [
        {
            "skill_id": "skill-1",
            "name": "Pirate Speak",
            "source": "imported",
            "trigger": "automatic",
            "similarity": 0.82,
            "script_ran": False,
            "below_floor": False,
        }
    ]


@pytest.mark.asyncio
async def test_get_message_trace_skills_used_empty_when_no_skill_matched():
    message_id = uuid4()
    store = AsyncMock()
    store.get_trace = AsyncMock(return_value=_trace())

    app = _make_app(store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/messages/{message_id}/trace",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json()["skills_used"] == []


@pytest.mark.asyncio
async def test_get_message_trace_includes_conductor_ledger():
    message_id = uuid4()
    store = AsyncMock()
    trace = _trace()
    trace.conductor_hint = [{"agent": "calendar", "intent": "read", "prompt": "tue"}]
    trace.conductor_ledger = [
        {"agent": "calendar", "status": "done"},
        {
            "agent": "messenger",
            "status": "awaiting_confirmation",
            "request_id": "req-1",
        },
    ]
    store.get_trace = AsyncMock(return_value=trace)

    app = _make_app(store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/messages/{message_id}/trace",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["conductor_hint"][0]["agent"] == "calendar"
    assert data["conductor_ledger"][1]["request_id"] == "req-1"


@pytest.mark.asyncio
async def test_get_message_trace_exposes_below_floor():
    skill_usage = SkillUsageTrace(
        skill_id="skill-1",
        name="Pirate Speak",
        source="imported",
        trigger="automatic",
        similarity=0.43,
        below_floor=True,
    )
    store = AsyncMock()
    store.get_trace = AsyncMock(return_value=_trace(skills_used=[skill_usage]))

    app = _make_app(store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/messages/{uuid4()}/trace",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.json()["skills_used"][0]["below_floor"] is True


def _tiered_trace() -> MessageTrace:
    trace = _trace()
    trace.tier = TierTrace(
        agent="companion", tier="simple", decided_by="system_one", model="haiku"
    )
    return trace


@pytest.mark.asyncio
async def test_get_message_trace_includes_tier():
    store = AsyncMock()
    store.get_trace = AsyncMock(return_value=_tiered_trace())

    app = _make_app(store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/messages/{uuid4()}/trace",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.json()["tier"] == {
        "agent": "companion",
        "tier": "simple",
        "decided_by": "system_one",
        "model": "haiku",
    }


@pytest.mark.asyncio
async def test_get_message_trace_tier_is_null_when_absent():
    store = AsyncMock()
    store.get_trace = AsyncMock(return_value=_trace())

    app = _make_app(store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/messages/{uuid4()}/trace",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.json()["tier"] is None


@pytest.mark.asyncio
async def test_get_message_traces_batch_carries_tier_on_the_trace_only():
    message_id = uuid4()
    store = AsyncMock()
    store.get_traces = AsyncMock(return_value={message_id: _tiered_trace()})

    app = _make_app(store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/messages/traces",
            params={"ids": [str(message_id)]},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    entry = resp.json()["traces"][0]
    assert "tier" not in entry
    assert entry["trace"]["tier"]["tier"] == "simple"
    assert entry["trace"]["tier"]["decided_by"] == "system_one"


async def test_a_trace_with_a_deduplicated_call_is_served() -> None:
    message_id = uuid4()
    trace = _trace()
    trace.tool_calls = [
        ToolCallTrace(
            name="cancel_reminder",
            result_snippet="approved once; not repeated",
            duration_ms=0,
            success=True,
            access="write",
            gate="duplicate",
        )
    ]
    store = AsyncMock()
    store.get_trace = AsyncMock(return_value=trace)

    async with AsyncClient(
        transport=ASGITransport(app=_make_app(store)), base_url="http://test"
    ) as client:
        resp = await client.get(f"/api/v0/messages/{message_id}/trace")

    assert resp.status_code == 200
    assert resp.json()["tool_calls"][0]["gate"] == "duplicate"


@pytest.mark.asyncio
async def test_tool_calls_carry_agent_and_call_index_and_never_undo_args() -> None:
    trace = _trace()
    trace.tool_calls = [
        ToolCallTrace(
            name="set_reminder",
            result_snippet="",
            duration_ms=4,
            success=True,
            access="write",
            agent="reminders",
            call_index=2,
            undo_args={"reminder_id": "secret"},
        ),
        ToolCallTrace(name="get_goals", result_snippet="", duration_ms=1, success=True),
    ]
    store = AsyncMock()
    store.get_trace = AsyncMock(return_value=trace)

    async with AsyncClient(
        transport=ASGITransport(app=_make_app(store)), base_url="http://test"
    ) as client:
        resp = await client.get(f"/api/v0/messages/{uuid4()}/trace")

    calls = resp.json()["tool_calls"]
    assert (calls[0]["agent"], calls[0]["call_index"]) == ("reminders", 2)
    assert (calls[1]["agent"], calls[1]["call_index"]) == (None, 0)
    assert "secret" not in resp.text and "undo_args" not in calls[0]


def test_tool_call_trace_schema_declares_agent_and_call_index() -> None:
    from ze_api.api.v0.messages.schemas import ToolCallTraceResponse
    from ze_api.api.ws.schemas import WsTraceUpdateFrame

    props = ToolCallTraceResponse.model_json_schema()["properties"]
    assert props["call_index"]["default"] == 0
    assert "agent" in props
    assert "ToolCallTraceResponse" in str(WsTraceUpdateFrame.model_json_schema())


@pytest.mark.asyncio
async def test_get_message_trace_carries_the_screen_trace():
    from ze_core.conversation.messages.types import ScreenTrace

    trace = _trace()
    trace.screen = ScreenTrace.from_dict(
        {
            "origin": "chat_about", "place": "doing", "route": "/doing/workflows/w1",
            "subject": ["Workflow · Weekly report"], "selection_count": 1, "visible_count": 13,
            "focused_module": "Workflows", "note_chars": 812, "invalid": [],
            "resolvers": [{"kind": "workflow", "id": "w1", "status": "ok", "ms": 14}],
        }
    )
    store = AsyncMock()
    store.get_trace = AsyncMock(return_value=trace)
    app = _make_app(store)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v0/messages/{uuid4()}/trace", headers={"Authorization": f"Bearer {API_KEY}"})
    screen = resp.json()["screen"]
    assert screen["origin"] == "chat_about" and screen["subject"] == ["Workflow · Weekly report"]
    assert screen["resolvers"] == [{"kind": "workflow", "id": "w1", "status": "ok", "ms": 14}]


@pytest.mark.asyncio
async def test_get_message_trace_screen_is_null_when_absent():
    store = AsyncMock()
    store.get_trace = AsyncMock(return_value=_trace())
    app = _make_app(store)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v0/messages/{uuid4()}/trace", headers={"Authorization": f"Bearer {API_KEY}"})
    assert resp.json()["screen"] is None
