import pytest
import yaml
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ze_api.api import dependencies
from ze_api.api.routes import memory, routing
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
    app.include_router(memory.router, prefix="/memory")
    app.include_router(routing.router, prefix="/routing")

    app.dependency_overrides[dependencies.get_container] = lambda: container
    app.dependency_overrides[dependencies.get_settings] = lambda: settings
    app.dependency_overrides[dependencies.require_api_key] = lambda: None

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


# ── GET /memory/digest ────────────────────────────────────────────────────────


def test_memory_digest_returns_structure(client):
    c, conn = client
    conn.fetch = AsyncMock(return_value=[])
    resp = c.get("/memory/digest")
    assert resp.status_code == 200
    data = resp.json()
    assert "unreviewed_facts" in data
    assert "contradicted_facts" in data
    assert "recent_episodes" in data


# ── GET /memory/facts ─────────────────────────────────────────────────────────


def test_memory_facts_returns_list(client):
    c, conn = client
    conn.fetch = AsyncMock(return_value=[])
    resp = c.get("/memory/facts")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_memory_fact_quality_has_no_raw_bucket(client):
    c, conn = client
    conn.fetchrow = AsyncMock(
        return_value={
            "total": 3,
            "avg_confidence": 0.8,
            "low_confidence_count": 0,
            "contradicted_count": 0,
            "synthesized_unreviewed": 1,
            "synthesized_uncorroborated": 1,
            "synthesized_expired": 0,
        }
    )
    conn.fetch = AsyncMock(
        return_value=[
            {"provenance": "prompt_supplied", "n": 2},
            {"provenance": "synthesized", "n": 1},
        ]
    )
    resp = c.get("/memory/facts/quality")
    assert resp.status_code == 200
    data = resp.json()
    assert "raw" not in data["by_provenance"]
    assert data["by_provenance"]["prompt_supplied"] == 2
    assert data["by_provenance"]["synthesized"] == 1


# ── OpenAPI schema ────────────────────────────────────────────────────────────


def test_openapi_includes_rest_paths(client):
    c, _ = client
    schema = c.get("/openapi.json").json()
    paths = schema["paths"]
    assert "/memory/facts" in paths
    assert "/memory/facts/review" in paths
    assert "/memory/digest" in paths
    assert "/routing/log" in paths
