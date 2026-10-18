"""GET /api/v0/system/models (Phase 194)."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.v0.system.models import router
from ze_api.settings import Settings, get_settings

API_KEY = "test-key"
SHIPPED_CONFIG = Path(__file__).resolve().parents[2] / "config" / "config.yaml"


class _Full:
    model = "vendor/full"
    model_simple = None


class _Tiered:
    model = "vendor/deep"
    model_simple = "vendor/cheap"


@pytest.fixture(autouse=True)
def agents(monkeypatch):
    registry = {"zeta": _Full, "alpha": _Tiered, "mid": _Full}
    monkeypatch.setattr(
        "ze_api.api.v0.system.models.get_enabled_agents", lambda: registry
    )
    monkeypatch.setattr("ze_core.routing.tier.get_enabled_agents", lambda: registry)


@pytest.fixture
def config_dir(tmp_path):
    shutil.copy(SHIPPED_CONFIG, tmp_path / "config.yaml")
    return tmp_path


def _settings(config_dir) -> Settings:
    get_settings.cache_clear()
    return Settings(
        openrouter_api_key="x",
        database_url="postgresql://ze:ze@localhost:5432/ze",
        config_dir=config_dir,
    )


def _edit(config_dir, mutate) -> None:
    path = config_dir / "config.yaml"
    data = yaml.safe_load(path.read_text())
    mutate(data["system_one"]["surfaces"]["complexity"])
    path.write_text(yaml.dump(data))


def _app(settings) -> FastAPI:
    app = FastAPI()
    app.state.container = SimpleNamespace(settings=settings)
    app.state.settings = SimpleNamespace(ze_api_key=API_KEY)
    app.include_router(router, prefix="/api/v0")
    return app


async def _get(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(
            "/api/v0/system/models", headers={"Authorization": f"Bearer {API_KEY}"}
        )


async def test_requires_auth():
    app = _app(SimpleNamespace(config={}))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/api/v0/system/models")).status_code == 401


async def test_shipped_config_is_enabled_at_the_calibrated_bar(config_dir):
    resp = await _get(_app(_settings(config_dir)))

    assert resp.status_code == 200
    body = resp.json()
    assert body["complexity_enabled"] is True
    assert body["simple_max"] == pytest.approx(0.4)


async def test_enabled_with_a_null_bar_reports_disabled(config_dir):
    _edit(config_dir, lambda block: block.update(simple_max=None))

    body = (await _get(_app(_settings(config_dir)))).json()

    assert body["complexity_enabled"] is False
    assert body["simple_max"] is None


async def test_agents_sorted_with_simple_model_only_when_declared(config_dir):
    body = (await _get(_app(_settings(config_dir)))).json()

    assert [a["name"] for a in body["agents"]] == ["alpha", "mid", "zeta"]
    by_name = {a["name"]: a for a in body["agents"]}
    assert by_name["alpha"]["model"] == "vendor/deep"
    assert by_name["alpha"]["model_simple"] == "vendor/cheap"
    assert by_name["zeta"]["model"] == "vendor/full"
    assert by_name["zeta"]["model_simple"] is None


async def test_model_overrides_apply_to_the_full_model(config_dir):
    path = config_dir / "config.yaml"
    data = yaml.safe_load(path.read_text())
    data.setdefault("models", {}).setdefault("overrides", {})["alpha"] = "vendor/forced"
    path.write_text(yaml.dump(data))

    body = (await _get(_app(_settings(config_dir)))).json()

    assert {a["name"]: a for a in body["agents"]}["alpha"]["model"] == "vendor/forced"


async def test_reloaded_settings_flip_the_flag(config_dir):
    container = SimpleNamespace(settings=_settings(config_dir))
    app = FastAPI()
    app.state.container = container
    app.state.settings = SimpleNamespace(ze_api_key=API_KEY)
    app.include_router(router, prefix="/api/v0")
    assert (await _get(app)).json()["complexity_enabled"] is True

    _edit(config_dir, lambda block: block.update(enabled=False))
    container.settings = _settings(config_dir)

    assert (await _get(app)).json()["complexity_enabled"] is False


async def test_response_carries_no_secret_keys(config_dir):
    raw = (await _get(_app(_settings(config_dir)))).text.lower()

    for word in ("key", "token", "secret"):
        assert word not in raw
