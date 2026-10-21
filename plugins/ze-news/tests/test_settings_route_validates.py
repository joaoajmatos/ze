from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_news.api.routes import router
from ze_plugin.api_auth import require_api_key


def _app() -> FastAPI:
    app = FastAPI()
    app.state.settings = SimpleNamespace(
        config={
            "news": {
                "enabled": True,
                "sources": [{"key": "bbc", "url": "u", "tags": []}],
            }
        }
    )
    app.dependency_overrides[require_api_key] = lambda: None
    app.include_router(router)
    return app


async def test_settings_route_validates_its_tree_before_returning():
    with patch("ze_news.api.routes.validate_plugin_tree") as check:
        async with AsyncClient(
            transport=ASGITransport(app=_app()), base_url="http://t"
        ) as c:
            resp = await c.get("/api/v0/news/settings")
    assert resp.status_code == 200
    check.assert_called_once()
    assert check.call_args.args[1] == resp.json()["tree"]
