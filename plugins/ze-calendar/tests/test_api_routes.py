from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_calendar.api.routes import router
from ze_plugin.api_auth import require_api_key

API_KEY = "test-key"

_PRIMITIVE_TYPE_NAMES = frozenset(
    {
        "col",
        "row",
        "text",
        "badge",
        "divider",
        "spacer",
        "button",
        "progress",
        "table",
        "form",
        "connections",
    }
)


def _assert_valid_tree(nodes: list) -> None:
    """Recursively verify every node carries a known primitive type."""
    for node in nodes:
        assert isinstance(node, dict), f"tree node must be a dict, got {type(node)}"
        assert "type" in node, f"tree node missing 'type': {node}"
        assert node["type"] in _PRIMITIVE_TYPE_NAMES, (
            f"unknown primitive type {node['type']!r}"
        )
        for child_key in ("children", "fields", "connections"):
            if child_key in node and isinstance(node[child_key], list):
                _assert_valid_tree(node[child_key])


def _make_app(store=None) -> FastAPI:
    app = FastAPI()
    app.state.container = SimpleNamespace(
        _plugin_stores={"reminder_store": store} if store is not None else {},
        settings=SimpleNamespace(ze_api_key=API_KEY),
    )
    app.state.settings = app.state.container.settings
    app.dependency_overrides[require_api_key] = lambda: None
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_get_reminders_page_returns_tree():
    store = AsyncMock()
    store.list_all = AsyncMock(return_value=[])
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/reminders/page", headers={"Authorization": f"Bearer {API_KEY}"}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Upcoming"
    assert isinstance(data["tree"], list)
    _assert_valid_tree(data["tree"])
    store.list_all.assert_awaited_once()


def _reminder(label, *, sent=False, sent_at=None, fire_hours=1):
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4

    from ze_calendar.reminders.store import Reminder

    fire = datetime(2026, 10, 17, 9, tzinfo=timezone.utc) + timedelta(hours=fire_hours)
    return Reminder(
        id=uuid4(),
        label=label,
        fire_at=fire,
        created_at=fire - timedelta(days=1),
        sent=sent,
        sent_at=sent_at,
    )


async def _get_reminders(store, **params):
    app = _make_app(store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(
            "/api/v0/reminders",
            params=params,
            headers={"Authorization": f"Bearer {API_KEY}"},
        )


@pytest.mark.asyncio
async def test_list_reminders_maps_status_from_sent_and_due():
    from datetime import datetime, timezone

    sent_at = datetime(2026, 10, 17, 8, tzinfo=timezone.utc)
    store = AsyncMock()
    store.list_by_status = AsyncMock(
        return_value=[
            (_reminder("future"), False),
            (_reminder("missed", fire_hours=-5), True),
            (_reminder("done", sent=True, sent_at=sent_at, fire_hours=-3), True),
        ]
    )

    resp = await _get_reminders(store, status="all")

    assert resp.status_code == 200
    body = resp.json()
    assert [(r["label"], r["status"]) for r in body] == [
        ("future", "upcoming"),
        ("missed", "overdue"),
        ("done", "fired"),
    ]
    assert body[0]["sent_at"] is None
    assert datetime.fromisoformat(body[2]["sent_at"]) == sent_at
    assert body[0]["fire_at"].endswith(("Z", "+00:00"))
    assert set(body[0]) == {"id", "label", "fire_at", "sent_at", "status"}


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["upcoming", "overdue", "fired", "all"])
async def test_status_filter_and_limit_reach_the_store(status):
    store = AsyncMock()
    store.list_by_status = AsyncMock(return_value=[])

    await _get_reminders(store, status=status, limit=999)

    store.list_by_status.assert_awaited_once_with(status, 200)


@pytest.mark.asyncio
async def test_defaults_to_upcoming_with_limit_fifty():
    store = AsyncMock()
    store.list_by_status = AsyncMock(return_value=[])
    await _get_reminders(store)
    store.list_by_status.assert_awaited_once_with("upcoming", 50)


@pytest.mark.asyncio
async def test_unknown_status_is_422():
    resp = await _get_reminders(AsyncMock(), status="weird")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_missing_store_returns_empty_list():
    resp = await _get_reminders(None)
    assert resp.status_code == 200 and resp.json() == []


@pytest.mark.asyncio
async def test_list_reminders_requires_api_key():
    app = _make_app(AsyncMock())
    app.dependency_overrides.clear()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v0/reminders")
    assert resp.status_code in (401, 403)
