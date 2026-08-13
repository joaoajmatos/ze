"""Tests for GET /api/v0/messages/traces batch endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.dependencies import get_message_store, require_api_key
from ze_api.api.messages import router
from ze_core.conversation.messages.types import (
    MemoryChunkTrace,
    MessageTrace,
    SkillUsageTrace,
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
