"""Tests for /api/v0/notifications routes."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.deps import require_api_key
from ze_api.api.v0.notifications.router import router
from ze_proactive.notification_store import InvalidCursorError
from ze_proactive.types import Notification

API_KEY = "test-key"


def _notification(**overrides) -> Notification:
    defaults = dict(
        id="notif-1",
        event_type="stuck_goal",
        source="goals",
        title="Goal stuck",
        body="Goal A hasn't moved in 3 days",
        target_type="goal",
        target_id="goal-a",
        created_at=datetime.now(timezone.utc),
        read=False,
    )
    defaults.update(overrides)
    return Notification(**defaults)


def _make_app(notification_store=None) -> tuple[FastAPI, AsyncMock]:
    app = FastAPI()
    store = notification_store or AsyncMock()
    container = SimpleNamespace(notification_store=store)
    app.state.container = container

    app.dependency_overrides[require_api_key] = lambda: None
    app.include_router(router, prefix="/api/v0")
    return app, store


@pytest.mark.asyncio
async def test_list_notifications_returns_items_and_cursor():
    store = AsyncMock()
    store.list_page = AsyncMock(return_value=([_notification()], "next-cursor"))
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/notifications",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["event_type"] == "stuck_goal"
    assert data["next_cursor"] == "next-cursor"


@pytest.mark.asyncio
async def test_list_notifications_carries_target_parent_id():
    store = AsyncMock()
    store.list_page = AsyncMock(
        return_value=(
            [
                _notification(
                    target_type="workflow_execution",
                    target_id="ex-1",
                    target_parent_id="wf-1",
                ),
                _notification(id="notif-2"),
            ],
            None,
        )
    )
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/notifications", headers={"Authorization": f"Bearer {API_KEY}"}
        )

    first, second = resp.json()["items"]
    assert first["target_parent_id"] == "wf-1"
    assert second["target_parent_id"] is None


@pytest.mark.asyncio
async def test_list_notifications_passes_query_params():
    store = AsyncMock()
    store.list_page = AsyncMock(return_value=([], None))
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/notifications",
            params={"unread_only": "true", "mark_read": "true", "limit": 5},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    store.list_page.assert_awaited_once_with(
        cursor=None,
        limit=5,
        unread_only=True,
        mark_read=True,
        delivery=None,
        push_class=None,
        since=None,
    )


@pytest.mark.asyncio
async def test_list_notifications_passes_outcome_filters():
    store = AsyncMock()
    store.list_page = AsyncMock(return_value=([], None))
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/notifications",
            params=[
                ("delivery", "held"),
                ("delivery", "suppressed"),
                ("push_class", "discretionary"),
                ("since", "2026-10-17T08:00:00+00:00"),
            ],
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    kwargs = store.list_page.await_args.kwargs
    assert kwargs["delivery"] == ["held", "suppressed"]
    assert kwargs["push_class"] == "discretionary"
    assert kwargs["since"].isoformat() == "2026-10-17T08:00:00+00:00"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params", [{"delivery": "bogus"}, {"push_class": "bogus"}, {"since": "not-a-date"}]
)
async def test_list_notifications_rejects_unknown_filter_values(params):
    store = AsyncMock()
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/notifications",
            params=params,
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 422
    store.list_page.assert_not_called()


@pytest.mark.asyncio
async def test_list_notifications_items_carry_urgency_and_delivered_at():
    delivered = datetime(2026, 10, 17, 9, tzinfo=timezone.utc)
    store = AsyncMock()
    store.list_page = AsyncMock(
        return_value=(
            [_notification(urgency="high", delivery="released", delivered_at=delivered)],
            None,
        )
    )
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/notifications", headers={"Authorization": f"Bearer {API_KEY}"}
        )

    item = resp.json()["items"][0]
    assert item["urgency"] == "high"
    assert datetime.fromisoformat(item["delivered_at"]) == delivered


@pytest.mark.asyncio
async def test_list_notifications_invalid_cursor_returns_400():
    store = AsyncMock()
    store.list_page = AsyncMock(side_effect=InvalidCursorError("bad"))
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/notifications",
            params={"cursor": "garbage"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_unread_count():
    store = AsyncMock()
    store.unread_count = AsyncMock(return_value=3)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/notifications/unread-count",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"count": 3}


@pytest.mark.asyncio
async def test_mark_notification_read_success():
    store = AsyncMock()
    store.mark_read = AsyncMock(return_value=True)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v0/notifications/notif-1/read",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_mark_notification_read_404_when_missing():
    store = AsyncMock()
    store.mark_read = AsyncMock(return_value=False)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v0/notifications/missing/read",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_mark_all_notifications_read():
    store = AsyncMock()
    store.mark_all_read = AsyncMock(return_value=12)
    app, _ = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v0/notifications/read-all",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"marked": 12}


@pytest.mark.asyncio
async def test_list_notifications_since_without_utc_offset_is_422():
    store = AsyncMock()
    app, _ = _make_app(store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/notifications",
            params={"since": "2026-10-17T08:00:00"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    assert resp.status_code == 422
    store.list_page.assert_not_called()
