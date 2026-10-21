"""Tests for GET /api/v0/ui/manifest."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.support.fixture_plugin import FixturePlugin
from ze_api.api.deps import require_api_key
from ze_api.api.v0.system.ui import ui_router as router
from ze_plugin.ui import UiManifest, collect_ui_contributions

API_KEY = "test-key"


def _make_app(manifest: UiManifest) -> FastAPI:
    app = FastAPI()
    app.state.container = SimpleNamespace(
        ui_manifest=manifest, settings=SimpleNamespace(ze_api_key=API_KEY)
    )
    app.state.settings = app.state.container.settings
    app.dependency_overrides[require_api_key] = lambda: None
    app.include_router(router, prefix="/api/v0")
    return app


async def _get(app: FastAPI) -> dict:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v0/ui/manifest", headers={"Authorization": f"Bearer {API_KEY}"}
        )
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_get_ui_manifest_returns_empty_lists():
    data = await _get(_make_app(collect_ui_contributions([])))
    assert data == {"modules": [], "presets": [], "settings_sections": []}


@pytest.mark.asyncio
async def test_get_ui_manifest_returns_modules_presets_and_settings():
    data = await _get(_make_app(collect_ui_contributions([FixturePlugin()])))
    assert {m["slot"] for m in data["modules"]} == {
        "mind.entity",
        "doing.run",
        "governance.connections",
    }
    assert data["modules"][0].keys() == {
        "id", "plugin", "label", "icon", "slot", "prompt",
        "settings_operation_id", "priority", "kind",
    }
    assert "provider" not in data["modules"][0]
    assert data["presets"][0]["prompt"] == "Show the fixture"
    assert data["settings_sections"][0]["settings_operation_id"] == "getNewsSettings"
    assert "nav" not in data
