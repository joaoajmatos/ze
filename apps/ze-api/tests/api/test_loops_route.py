"""Integration-style tests for /api/v0/loops routes (Phase 109)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.deps import require_api_key
from ze_api.api.v0.loops.router import router
from ze_plugin.contribution import EvidenceRef
from ze_worldstate.errors import InvalidLoopTransitionError, LoopNotFoundError
from ze_worldstate.lifecycle import LoopLifecycle
from ze_worldstate.types import (
    LoopProvenance,
    LoopSource,
    LoopSourceRole,
    LoopState,
    OpenLoop,
    SourceKey,
)

API_KEY = "test-key"


def _loop(**overrides) -> OpenLoop:
    defaults = dict(
        id=uuid4(),
        title="Renew passport before the trip",
        provenance=LoopProvenance.CONVERSATION,
        confidence=0.35,
        state=LoopState.SUSPECTED,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return OpenLoop(**defaults)


def _source(
    loop_id,
    *,
    role=LoopSourceRole.CORROBORATION,
    inflow="email",
    ref="G1",
    same_concern=None,
    promoted=False,
) -> LoopSource:
    return LoopSource(
        loop_id=loop_id,
        role=role,
        key=SourceKey(inflow, ref),
        evidence=EvidenceRef(kind="episode", id=uuid4()),
        same_concern=same_concern,
        promoted=promoted,
        created_at=datetime.now(timezone.utc),
    )


def _make_app(loop_store=None, lifecycle=None) -> tuple[FastAPI, AsyncMock]:
    app = FastAPI()
    store = loop_store or AsyncMock()
    lifecycle = lifecycle or AsyncMock(spec=LoopLifecycle)
    container = SimpleNamespace(loop_store=store, loop_lifecycle=lifecycle)
    app.state.container = container

    app.dependency_overrides[require_api_key] = lambda: None
    app.include_router(router, prefix="/api/v0")
    return app, store


@pytest.mark.asyncio
async def test_list_loops_defaults_to_non_terminal_states():
    store = AsyncMock()
    store.list = AsyncMock(return_value=[_loop()])
    store.list_sources_for = AsyncMock(return_value={})
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/loops", headers={"Authorization": f"Bearer {API_KEY}"}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["state"] == "suspected"
    store.list.assert_awaited_once_with(["suspected", "active", "drifting"], since=None)


@pytest.mark.asyncio
async def test_claim_kind_follows_state_and_is_null_for_a_dropped_loop():
    store = AsyncMock()
    store.list = AsyncMock(
        return_value=[
            _loop(state=LoopState.SUSPECTED),
            _loop(state=LoopState.ACTIVE),
            _loop(state=LoopState.DROPPED),
        ]
    )
    store.list_sources_for = AsyncMock(return_value={})
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/loops", headers={"Authorization": f"Bearer {API_KEY}"}
        )

    assert resp.status_code == 200
    assert [item["claim_kind"] for item in resp.json()] == [
        "suspicion",
        "priority",
        None,
    ]


@pytest.mark.asyncio
async def test_list_loops_reports_promotion_and_source_inflows():
    loop = _loop(state=LoopState.ACTIVE)
    store = AsyncMock()
    store.list = AsyncMock(return_value=[loop])
    store.list_sources_for = AsyncMock(
        return_value={
            loop.id: [
                _source(loop.id, role=LoopSourceRole.ORIGIN, inflow="conversation"),
                _source(loop.id, inflow="email", same_concern=0.93, promoted=True),
            ]
        }
    )
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/loops", headers={"Authorization": f"Bearer {API_KEY}"}
        )

    assert resp.status_code == 200
    item = resp.json()[0]
    assert item["promoted"] is True
    assert item["source_inflows"] == ["conversation", "email"]
    store.list_sources_for.assert_awaited_once_with([loop.id])


@pytest.mark.asyncio
async def test_list_exposes_reminder_and_goal_ids():
    reminder_id, goal_id = uuid4(), uuid4()
    linked = _loop(reminder_id=reminder_id, goal_id=goal_id)
    unlinked = _loop()
    store = AsyncMock()
    store.list = AsyncMock(return_value=[linked, unlinked])
    store.list_sources_for = AsyncMock(return_value={})
    app, _ = _make_app(store)
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        listed = await client.get("/api/v0/loops", headers=headers)

    assert listed.status_code == 200
    first, second = listed.json()
    assert (first["reminder_id"], first["goal_id"]) == (
        str(reminder_id),
        str(goal_id),
    )
    assert (second["reminder_id"], second["goal_id"]) == (None, None)


@pytest.mark.asyncio
async def test_confirm_and_close_go_through_the_lifecycle():
    loop = _loop()
    lifecycle = AsyncMock(spec=LoopLifecycle)
    lifecycle.confirm.return_value = _loop(
        id=loop.id, state=LoopState.ACTIVE, confidence=0.9
    )
    lifecycle.close.return_value = _loop(id=loop.id, state=LoopState.CLOSED)
    app, store = _make_app(lifecycle=lifecycle)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        confirm_resp = await client.post(
            f"/api/v0/loops/{loop.id}/confirm",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        assert confirm_resp.status_code == 200
        assert confirm_resp.json()["state"] == "active"
        assert confirm_resp.json()["confidence"] == 0.9

        close_resp = await client.post(
            f"/api/v0/loops/{loop.id}/close",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        assert close_resp.status_code == 200
        assert close_resp.json()["state"] == "closed"

    lifecycle.confirm.assert_awaited_once_with(loop.id)
    lifecycle.close.assert_awaited_once_with(loop.id)
    assert store.method_calls == []


@pytest.mark.asyncio
async def test_drop_goes_through_the_lifecycle():
    loop = _loop()
    lifecycle = AsyncMock(spec=LoopLifecycle)
    lifecycle.drop.return_value = _loop(id=loop.id, state=LoopState.DROPPED)
    app, store = _make_app(lifecycle=lifecycle)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/loops/{loop.id}/drop",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json()["state"] == "dropped"
    lifecycle.drop.assert_awaited_once_with(loop.id)
    assert store.method_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event", "route"),
    [("confirm", "confirm"), ("close", "close"), ("drop", "drop")],
)
async def test_invalid_transition_returns_409(event, route):
    lifecycle = AsyncMock(spec=LoopLifecycle)
    getattr(lifecycle, event).side_effect = InvalidLoopTransitionError("nope")
    app, _ = _make_app(lifecycle=lifecycle)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/loops/{uuid4()}/{route}",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 409
    assert resp.json()["detail"] == "nope"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event", "route"),
    [("confirm", "confirm"), ("close", "close"), ("drop", "drop")],
)
async def test_transition_404_when_missing(event, route):
    lifecycle = AsyncMock(spec=LoopLifecycle)
    getattr(lifecycle, event).side_effect = LoopNotFoundError("missing")
    app, _ = _make_app(lifecycle=lifecycle)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/loops/{uuid4()}/{route}",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_reflects_the_stored_confidence_not_a_cached_one():
    """SC-006: a confidence the lifecycle lowered shows on the next GET /loops."""
    from ze_agents.claims import CONFIDENCE_FLOOR

    loop = _loop(confidence=0.6)
    store = AsyncMock()
    store.list = AsyncMock(return_value=[loop])
    store.list_sources_for = AsyncMock(return_value={})
    app, _ = _make_app(store)

    loop.confidence = CONFIDENCE_FLOOR

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/loops", headers={"Authorization": f"Bearer {API_KEY}"}
        )

    assert resp.status_code == 200
    assert resp.json()[0]["confidence"] == CONFIDENCE_FLOOR


async def _list(store, params):
    store.list_sources_for = AsyncMock(return_value={})
    app, _ = _make_app(store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(
            "/api/v0/loops",
            params=params,
            headers={"Authorization": f"Bearer {API_KEY}"},
        )


@pytest.mark.asyncio
async def test_state_is_repeatable():
    store = AsyncMock()
    store.list = AsyncMock(return_value=[])

    resp = await _list(store, [("state", "closed"), ("state", "dropped")])

    assert resp.status_code == 200
    store.list.assert_awaited_once_with(["closed", "dropped"], since=None)


@pytest.mark.asyncio
async def test_since_passes_through_and_combines_with_state():
    store = AsyncMock()
    store.list = AsyncMock(return_value=[])

    resp = await _list(
        store,
        [("state", "closed"), ("state", "dropped"), ("since", "2026-10-11T00:00:00Z")],
    )

    assert resp.status_code == 200
    store.list.assert_awaited_once_with(
        ["closed", "dropped"], since=datetime(2026, 10, 11, tzinfo=timezone.utc)
    )


@pytest.mark.asyncio
async def test_invalid_since_is_422():
    store = AsyncMock()
    store.list = AsyncMock(return_value=[])

    resp = await _list(store, {"since": "last tuesday"})

    assert resp.status_code == 422
    store.list.assert_not_called()
