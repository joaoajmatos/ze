import pytest
import yaml
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ze_api.api import deps
from ze_api.api.v0.memory import router as memory
from ze_api.api.eval import routing as routing
from ze_logging import configure_logging
from ze_api.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def setup_logging():
    configure_logging()


def make_settings(config_dir):
    get_settings.cache_clear()
    return Settings(
        openrouter_api_key="test-key",
        database_url="postgresql://ze:ze@localhost:5432/ze",
        database_url_sync="postgresql+psycopg2://ze:ze@localhost:5432/ze",
        config_dir=config_dir,
    )


@pytest.fixture
def config_dir(tmp_path):
    (tmp_path / "config.yaml").write_text(yaml.dump({"agents": {}}))
    return tmp_path


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.fixture
def client(mock_pool, config_dir):
    pool, conn = mock_pool
    settings = make_settings(config_dir)

    container = SimpleNamespace(pool=pool)

    app = FastAPI()
    app.state.container = container
    app.include_router(memory.router)
    app.include_router(routing.router)

    app.dependency_overrides[deps.get_container] = lambda: container
    app.dependency_overrides[deps.get_settings] = lambda: settings
    app.dependency_overrides[deps.require_api_key] = lambda: None

    with TestClient(app) as c:
        yield c, conn


# ── GET /routing/log ──────────────────────────────────────────────────────────


def test_get_routing_log_returns_list(client):
    c, conn = client
    conn.fetch = AsyncMock(return_value=[])
    resp = c.get("/routing/log")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_routing_log_respects_limit(client):
    c, conn = client
    conn.fetch = AsyncMock(return_value=[])
    resp = c.get("/routing/log?limit=10&offset=5")
    assert resp.status_code == 200


def test_get_routing_log_invalid_limit(client):
    c, _ = client
    resp = c.get("/routing/log?limit=0")
    assert resp.status_code == 422


# ── OpenAPI schema ────────────────────────────────────────────────────────────


def test_openapi_includes_rest_paths(client):
    c, _ = client
    schema = c.get("/openapi.json").json()
    paths = schema["paths"]
    assert "/memory/feed" in paths
    assert "/memory/facts/review" in paths
    assert "/memory/digest" not in paths
    assert "/routing/log" in paths


# ── Mind reads (phase 189) ────────────────────────────────────────────────────


def test_feed_items_carry_claim_kind(client):
    from datetime import datetime, timezone
    from uuid import uuid4

    c, conn = client
    conn.fetchrow = AsyncMock(return_value={"total_facts": 1, "total_episodes": 0})
    conn.fetch = AsyncMock(
        return_value=[
            {
                "id": uuid4(),
                "type": "fact",
                "key": "works_at",
                "value": "Acme",
                "confidence": 0.9,
                "reviewed": False,
                "contradicted": False,
                "provenance": "user_stated",
                "claim_kind": "identity",
                "summary": None,
                "prompt_snippet": None,
                "agent": "companion",
                "created_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
            }
        ]
    )
    resp = c.get("/memory/feed")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["claim_kind"] == "identity"


def test_entity_detail_exposes_claim_fields_and_neighbour_total(client):
    from datetime import datetime, timezone
    from uuid import uuid4

    c, conn = client
    eid = uuid4()
    conn.fetchrow = AsyncMock(
        return_value={
            "id": eid,
            "entity_type": "person",
            "canonical_name": "Ada",
            "aliases": [],
            "attrs": {},
            "degree": 0,
        }
    )
    conn.fetchval = AsyncMock(return_value=25)
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "id": uuid4(),
                    "key": "likes",
                    "value": "tea",
                    "agent": "companion",
                    "created_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
                    "claim_kind": "fact",
                    "confidence": 0.7,
                    "reviewed": False,
                    "contradicted": False,
                    "provenance": "user_stated",
                }
            ],
            [],
            [],
            [],
        ]
    )
    body = c.get(f"/memory/graph/entity/{eid}").json()
    assert body["neighbour_total"] == 25
    assert body["facts"][0]["claim_kind"] == "fact"
    assert body["facts"][0]["confidence"] == 0.7


def test_search_entities_returns_nodes(client):
    from uuid import uuid4

    c, conn = client
    conn.fetch = AsyncMock(
        return_value=[
            {
                "id": uuid4(),
                "entity_type": "person",
                "canonical_name": "Ada",
                "aliases": [],
                "attrs": {},
                "degree": 2,
            }
        ]
    )
    resp = c.get("/memory/entities", params={"q": "ad"})
    assert resp.status_code == 200
    assert resp.json()[0]["canonical_name"] == "Ada"


@pytest.mark.parametrize(
    "params",
    [{"q": ""}, {"q": "x" * 81}, {"q": "a", "limit": 0}, {"q": "a", "limit": 51}, {}],
)
def test_search_entities_validates_params(client, params):
    c, _ = client
    assert c.get("/memory/entities", params=params).status_code == 422


def test_search_entities_requires_api_key(config_dir):
    settings = make_settings(config_dir)
    settings.ze_api_key = "secret"
    app = FastAPI()
    app.state.settings = settings
    app.include_router(memory.router)
    app.dependency_overrides[deps.get_container] = lambda: SimpleNamespace(pool=MagicMock())
    with TestClient(app) as c:
        assert c.get("/memory/entities", params={"q": "a"}).status_code == 401
