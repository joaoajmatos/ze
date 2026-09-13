"""Integration-style tests for /api/v0/priority routes (Phase 127)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from ze_agents.claims import ClaimKind, Confidence, DecayProfile

from ze_api.api.dependencies import require_api_key
from ze_api.api.routes.priority import router
from ze_priority.errors import PriorityOverrideNotFoundError
from ze_priority.types import PriorityItem, PriorityRanking

API_KEY = "test-key"
UTC = timezone.utc


def _item(title: str, rank: int) -> PriorityItem:
    return PriorityItem(
        source_kind="loop",
        claim_kind=ClaimKind.PRIORITY,
        source_id=uuid4(),
        title=title,
        signal=None,
        priority=Confidence(
            value=1.0 - rank * 0.1, decay_profile=DecayProfile.TIME_LINEAR
        ),
        rank=rank,
        activity_at=datetime.now(UTC),
    )


def _make_app(
    priority_view=None, override_store=None, collision_store=None, nli_client=None
) -> FastAPI:
    app = FastAPI()
    app.state.container = SimpleNamespace(
        priority_view=priority_view or AsyncMock(),
        priority_override_store=override_store or AsyncMock(),
        collision_store=collision_store or AsyncMock(),
        nli_client=nli_client or AsyncMock(),
    )
    app.dependency_overrides[require_api_key] = lambda: None
    app.include_router(router, prefix="/api/v0")
    return app


@pytest.mark.asyncio
async def test_snapshot_returns_empty_list_when_nothing_open():
    view = AsyncMock()
    view.rank.return_value = PriorityRanking(
        items=[],
        sources_succeeded={"loop", "goal", "hypothesis"},
        sources_failed=set(),
        generated_at=datetime.now(UTC),
    )
    override_store = AsyncMock()
    override_store.get_active.return_value = []
    app = _make_app(priority_view=view, override_store=override_store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/priority/snapshot", headers={"Authorization": f"Bearer {API_KEY}"}
        )

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_snapshot_matches_response_shape():
    item = _item("Follow up with Maria", 1)
    view = AsyncMock()
    view.rank.return_value = PriorityRanking(
        items=[item],
        sources_succeeded={"loop", "goal", "hypothesis"},
        sources_failed=set(),
        generated_at=datetime.now(UTC),
    )
    override_store = AsyncMock()
    override_store.get_active.return_value = []
    app = _make_app(priority_view=view, override_store=override_store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/priority/snapshot", headers={"Authorization": f"Bearer {API_KEY}"}
        )

    assert resp.status_code == 200
    row = resp.json()[0]
    assert set(row) == {
        "source_kind",
        "source_id",
        "title",
        "displayed_rank",
        "computed_rank",
        "overridden_from_computed",
        "override",
    }
    assert row["override"] is None


@pytest.mark.asyncio
async def test_submit_override_404_on_stale_target():
    view = AsyncMock()
    view.rank.return_value = PriorityRanking(
        items=[],
        sources_succeeded={"loop", "goal", "hypothesis"},
        sources_failed=set(),
        generated_at=datetime.now(UTC),
    )
    app = _make_app(priority_view=view)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v0/priority/override",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "source_kind": "loop",
                "source_id": str(uuid4()),
                "anchor_source_kind": "loop",
                "anchor_source_id": str(uuid4()),
                "relation": "above",
            },
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_submit_override_success_returns_snapshot_row():
    target, anchor = _item("target", 2), _item("anchor", 1)
    view = AsyncMock()
    view.rank.return_value = PriorityRanking(
        items=[anchor, target],
        sources_succeeded={"loop", "goal", "hypothesis"},
        sources_failed=set(),
        generated_at=datetime.now(UTC),
    )
    override_store = AsyncMock()
    override_store.create.side_effect = lambda o: o
    override_store.get_active.return_value = []
    app = _make_app(priority_view=view, override_store=override_store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v0/priority/override",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "source_kind": target.source_kind,
                "source_id": str(target.source_id),
                "anchor_source_kind": anchor.source_kind,
                "anchor_source_id": str(anchor.source_id),
                "relation": "above",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["source_id"] == str(target.source_id)
    override_store.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_unpin_404_when_no_active_override():
    override_store = AsyncMock()
    override_store.unpin.side_effect = PriorityOverrideNotFoundError("nope")
    app = _make_app(override_store=override_store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/priority/override/{uuid4()}/unpin",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unpin_success_returns_snapshot_row():
    item = _item("target", 1)
    view = AsyncMock()
    view.rank.return_value = PriorityRanking(
        items=[item],
        sources_succeeded={"loop", "goal", "hypothesis"},
        sources_failed=set(),
        generated_at=datetime.now(UTC),
    )
    override_store = AsyncMock()
    from ze_priority.types import PriorityOverride

    stored_override = PriorityOverride(
        id=uuid4(),
        source_kind=item.source_kind,
        source_id=item.source_id,
        anchor_source_kind=item.source_kind,
        anchor_source_id=uuid4(),
        relation="above",
        pinned=False,
        submitted_at=datetime.now(UTC),
        superseded_at=None,
        contribution_domain_id=uuid4(),
    )
    override_store.unpin.return_value = stored_override
    override_store.get_active.return_value = [stored_override]
    app = _make_app(priority_view=view, override_store=override_store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/priority/override/{stored_override.id}/unpin",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json()["source_id"] == str(item.source_id)
