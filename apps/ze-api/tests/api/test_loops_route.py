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
from ze_worldstate.types import (
    LoopClaimKind,
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
        claim_kind=LoopClaimKind.SUSPICION,
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


def _make_app(loop_store=None) -> tuple[FastAPI, AsyncMock]:
    app = FastAPI()
    store = loop_store or AsyncMock()
    container = SimpleNamespace(loop_store=store)
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
    store.list.assert_awaited_once_with(["suspected", "active", "drifting"])


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
async def test_confirm_close_drop_persist_across_relist():
    loop = _loop()
    store = AsyncMock()

    async def _transition(loop_id, state):
        target = LoopState(state)
        confirmed_at = (
            datetime.now(timezone.utc) if target == LoopState.ACTIVE else None
        )
        return _loop(id=loop_id, state=target, confirmed_at=confirmed_at)

    store.transition = AsyncMock(side_effect=_transition)
    store.list_evidence = AsyncMock(return_value=[])
    store.set_dismissed_evidence_fingerprint = AsyncMock()
    app, _ = _make_app(store)

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


@pytest.mark.asyncio
async def test_drop_records_fingerprint_and_persists():
    loop = _loop()
    store = AsyncMock()
    store.list_evidence = AsyncMock(return_value=[])
    store.transition = AsyncMock(
        return_value=_loop(id=loop.id, state=LoopState.DROPPED)
    )
    store.set_dismissed_evidence_fingerprint = AsyncMock()
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/loops/{loop.id}/drop",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json()["state"] == "dropped"
    store.set_dismissed_evidence_fingerprint.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalid_transition_returns_409():
    store = AsyncMock()
    store.transition = AsyncMock(side_effect=InvalidLoopTransitionError("nope"))
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/loops/{uuid4()}/confirm",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_confidence_decay_reflected_on_next_list():
    """SC-006 / quickstart's evidence-retraction-cascade scenario, exercised through
    the REST surface: once ze_worldstate.decay.cascade_from_evidence has lowered a
    loop's stored confidence (unit-tested directly in test_decay.py), the next
    GET /api/v0/loops must reflect the new value — not a cached one.
    """
    from ze_agents.claims import CONFIDENCE_FLOOR
    from ze_worldstate.decay import cascade_from_evidence

    loop = _loop(confidence=0.6)
    store = AsyncMock()
    store.list_by_evidence = AsyncMock(return_value=[loop])
    store.count_evidence_links = AsyncMock(return_value=1)
    store.set_confidence = AsyncMock(
        side_effect=lambda loop_id, c: setattr(loop, "confidence", c)
    )
    store.list = AsyncMock(return_value=[loop])
    store.list_sources_for = AsyncMock(return_value={})
    app, _ = _make_app(store)

    await cascade_from_evidence("fact", uuid4(), store)
    assert loop.confidence == CONFIDENCE_FLOOR

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/loops", headers={"Authorization": f"Bearer {API_KEY}"}
        )

    assert resp.status_code == 200
    assert resp.json()[0]["confidence"] == CONFIDENCE_FLOOR


@pytest.mark.asyncio
async def test_transition_404_when_missing():
    store = AsyncMock()
    store.transition = AsyncMock(side_effect=LoopNotFoundError("missing"))
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/loops/{uuid4()}/close",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 404
