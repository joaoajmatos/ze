from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ze_api.api.routes import health


def _client(api_key: str = "secret") -> TestClient:
    app = FastAPI()
    app.state.settings = SimpleNamespace(ze_api_key=api_key)
    app.include_router(health.router)
    return TestClient(app)


def test_health_returns_ok_with_valid_bearer():
    client = _client()
    resp = client.get("/api/health", headers={"Authorization": "Bearer secret"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_rejects_invalid_bearer():
    client = _client()
    resp = client.get("/api/health", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_health_rejects_missing_auth():
    client = _client()
    resp = client.get("/api/health")
    assert resp.status_code == 401
