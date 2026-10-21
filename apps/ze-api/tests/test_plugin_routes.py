"""Runtime plugin routes and the OpenAPI export share one source of routers."""

from __future__ import annotations

import pytest
from fastapi import APIRouter, FastAPI

from ze_api.errors import PluginRouteDriftError
from ze_api.wiring.plugin_routes import (
    collect_static_plugin_routers,
    mount_plugin_routers,
)


class _Plugin:
    def __init__(self, routers: list) -> None:
        self._routers = routers

    def rest_routes(self) -> list:
        return self._routers


def test_mounts_routers_that_the_export_knows():
    static = collect_static_plugin_routers()
    app = FastAPI()
    mount_plugin_routers(app, [_Plugin(static)])
    paths = {route.path for route in app.routes}
    assert "/api/v0/news/settings" in paths


def test_a_disabled_plugin_that_returns_no_routes_mounts_nothing():
    app = FastAPI()
    before = len(app.routes)
    mount_plugin_routers(app, [_Plugin([])])
    assert len(app.routes) == before


def test_a_router_missing_from_the_export_fails_startup():
    stray = APIRouter()

    @stray.get("/api/v0/stray")
    def stray_route() -> dict:
        return {}

    with pytest.raises(PluginRouteDriftError):
        mount_plugin_routers(FastAPI(), [_Plugin([stray])])


def test_the_export_collector_is_the_runtime_collector():
    from ze_api.cli import openapi_export

    assert openapi_export.collect_static_plugin_routers is collect_static_plugin_routers
