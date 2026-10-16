"""Debug and eval routes are mounted only in eval mode, and use the bearer key."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from ze_api.api.app import create_app
from ze_api.settings import get_settings

EVAL_ONLY_PATHS = {
    "/eval/chat",
    "/eval/confirm",
    "/api/v0/collisions",
    "/api/v0/routing/log",
}


@pytest.fixture
def make_app(monkeypatch):
    def _make(eval_mode: bool):
        monkeypatch.setenv("EVAL_MODE", "true" if eval_mode else "false")
        get_settings.cache_clear()
        return create_app()

    yield _make
    get_settings.cache_clear()


def test_debug_routes_are_absent_outside_eval_mode(make_app):
    paths = set(make_app(eval_mode=False).openapi()["paths"])
    assert not EVAL_ONLY_PATHS & paths


def test_debug_routes_are_mounted_in_eval_mode(make_app):
    paths = set(make_app(eval_mode=True).openapi()["paths"])
    assert EVAL_ONLY_PATHS <= paths


def test_eval_operations_have_explicit_camel_case_ids(make_app):
    paths = make_app(eval_mode=True).openapi()["paths"]
    assert paths["/eval/chat"]["post"]["operationId"] == "evalChat"
    assert paths["/eval/confirm"]["post"]["operationId"] == "evalConfirm"


@pytest.mark.parametrize(
    ("headers", "status"),
    [
        ({}, 401),
        ({"x-ze-api-key": "k"}, 401),
        ({"Authorization": "Bearer nope"}, 401),
    ],
)
async def test_eval_chat_rejects_anything_but_the_bearer_key(make_app, headers, status):
    app = make_app(eval_mode=True)
    app.state.settings = SimpleNamespace(ze_api_key="k", eval_mode=True)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/eval/chat", json={"prompt": "hi"}, headers=headers)
    assert resp.status_code == status
