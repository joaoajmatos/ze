"""Tests for GET/PUT /api/v0/notifications/quiet-hours (Phase 177, T028)."""

from __future__ import annotations

from datetime import datetime, time, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.deps import (
    get_interruption_settings_store,
    get_notification_store,
    get_notifier,
    require_api_key,
)
from ze_api.api.v0.notifications.router import router
from ze_proactive.types import Notification, QuietHoursSetting

API_KEY = "test-key"


def _setting(**overrides) -> QuietHoursSetting:
    defaults = dict(
        enabled=False,
        start=None,
        end=None,
        timezone=None,
        updated_at=None,
    )
    defaults.update(overrides)
    return QuietHoursSetting(**defaults)


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
        push_class="discretionary",
        urgency="normal",
        delivery="suppressed",
    )
    defaults.update(overrides)
    return Notification(**defaults)


class _Env:
    def __init__(self, setting=None, *, held=0, max_per_day=5, upsert_result=None):
        self.settings = AsyncMock()
        self.settings.get = AsyncMock(return_value=setting or _setting())
        self.settings.upsert = AsyncMock(return_value=upsert_result or setting or _setting())
        self.notifications = AsyncMock()
        self.notifications.count_held = AsyncMock(return_value=held)
        self.notifications.list_page = AsyncMock(return_value=([], None))
        self.notifier = SimpleNamespace(max_discretionary_per_day=max_per_day)

    def client(self) -> AsyncClient:
        app = FastAPI()
        app.dependency_overrides[require_api_key] = lambda: None
        app.dependency_overrides[get_interruption_settings_store] = lambda: self.settings
        app.dependency_overrides[get_notification_store] = lambda: self.notifications
        app.dependency_overrides[get_notifier] = lambda: self.notifier
        app.include_router(router, prefix="/api/v0")
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_get_with_no_row_returns_defaults():
    env = _Env()
    async with env.client() as c:
        resp = await c.get("/api/v0/notifications/quiet-hours")
    assert resp.status_code == 200
    assert resp.json() == {
        "enabled": False,
        "start": None,
        "end": None,
        "timezone": None,
        "active_now": False,
        "held_count": 0,
        "max_discretionary_per_day": 5,
    }


@pytest.mark.asyncio
async def test_get_returns_saved_setting():
    env = _Env(
        _setting(
            enabled=True,
            start=time(23, 0),
            end=time(8, 0),
            timezone="Europe/Lisbon",
        ),
        held=2,
        max_per_day=5,
    )
    async with env.client() as c:
        resp = await c.get("/api/v0/notifications/quiet-hours")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["start"] == "23:00"
    assert body["end"] == "08:00"
    assert body["timezone"] == "Europe/Lisbon"
    assert isinstance(body["active_now"], bool)
    assert body["held_count"] == 2
    assert body["max_discretionary_per_day"] == 5


@pytest.mark.asyncio
async def test_put_round_trip_saves_window():
    stored = _setting(
        enabled=True,
        start=time(23, 0),
        end=time(8, 0),
        timezone="Europe/Lisbon",
    )
    env = _Env(upsert_result=stored, held=1)
    async with env.client() as c:
        resp = await c.put(
            "/api/v0/notifications/quiet-hours",
            json={
                "enabled": True,
                "start": "23:00",
                "end": "08:00",
                "timezone": "Europe/Lisbon",
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["start"] == "23:00"
    assert body["end"] == "08:00"
    assert body["timezone"] == "Europe/Lisbon"
    assert body["held_count"] == 1
    env.settings.upsert.assert_awaited_once_with(
        True, time(23, 0), time(8, 0), "Europe/Lisbon"
    )


@pytest.mark.asyncio
async def test_put_disabled_keeps_times():
    stored = _setting(
        enabled=False,
        start=time(23, 0),
        end=time(8, 0),
        timezone="Europe/Lisbon",
    )
    env = _Env(upsert_result=stored)
    async with env.client() as c:
        resp = await c.put(
            "/api/v0/notifications/quiet-hours",
            json={
                "enabled": False,
                "start": "23:00",
                "end": "08:00",
                "timezone": "Europe/Lisbon",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    env.settings.upsert.assert_awaited_once_with(
        False, time(23, 0), time(8, 0), "Europe/Lisbon"
    )


def _locs(resp) -> list[list[str]]:
    return [d["loc"] for d in resp.json()["detail"]]


@pytest.mark.asyncio
async def test_put_enabled_without_fields_is_422_on_each_field():
    env = _Env()
    async with env.client() as c:
        resp = await c.put(
            "/api/v0/notifications/quiet-hours",
            json={"enabled": True},
        )
    assert resp.status_code == 422
    locs = _locs(resp)
    assert ["body", "start"] in locs
    assert ["body", "end"] in locs
    assert ["body", "timezone"] in locs


@pytest.mark.asyncio
async def test_put_start_equals_end_is_422():
    env = _Env()
    async with env.client() as c:
        resp = await c.put(
            "/api/v0/notifications/quiet-hours",
            json={
                "enabled": True,
                "start": "23:00",
                "end": "23:00",
                "timezone": "Europe/Lisbon",
            },
        )
    assert resp.status_code == 422
    assert ["body", "end"] in _locs(resp)


@pytest.mark.asyncio
async def test_put_bad_time_is_422_on_start():
    env = _Env()
    async with env.client() as c:
        resp = await c.put(
            "/api/v0/notifications/quiet-hours",
            json={
                "enabled": True,
                "start": "25:00",
                "end": "08:00",
                "timezone": "Europe/Lisbon",
            },
        )
    assert resp.status_code == 422
    assert ["body", "start"] in _locs(resp)


@pytest.mark.asyncio
async def test_put_bad_timezone_is_422():
    env = _Env()
    async with env.client() as c:
        resp = await c.put(
            "/api/v0/notifications/quiet-hours",
            json={
                "enabled": True,
                "start": "23:00",
                "end": "08:00",
                "timezone": "Mars/Olympus",
            },
        )
    assert resp.status_code == 422
    assert ["body", "timezone"] in _locs(resp)


@pytest.mark.asyncio
async def test_list_notifications_includes_push_class_and_delivery():
    env = _Env()
    env.notifications.list_page = AsyncMock(return_value=([_notification()], None))
    async with env.client() as c:
        resp = await c.get("/api/v0/notifications")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["push_class"] == "discretionary"
    assert item["delivery"] == "suppressed"


def test_ze_container_exposes_notifier_and_interruption_settings_store():
    """get_notifier/get_interruption_settings_store read these off the container.

    The route tests above pass only because they override the dependencies; guard
    the real container so the wired app cannot AttributeError in production.
    """
    import inspect

    from ze_api.wiring.container import ZeContainer

    params = inspect.signature(ZeContainer).parameters
    assert "notifier" in params
    assert "interruption_settings_store" in params
