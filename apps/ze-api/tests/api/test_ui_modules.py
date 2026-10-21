"""Tests for GET /api/v0/ui/modules/{module_id}."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from structlog.testing import capture_logs

from tests.support.fixture_plugin import (
    FixturePlugin,
    register_fixture_agent,
    unregister_fixture_agent,
)
from ze_api.api.deps import require_api_key
from ze_api.api.v0.ui_modules import router as module_router
from ze_api.api.v0.ui_modules.router import router
from ze_plugin.ui import ModuleResult, ModuleSubject, collect_ui_contributions

API_KEY = "test-key"
ENTITY = uuid4()
RUN = uuid4()
WORKFLOW = uuid4()


@pytest.fixture(autouse=True)
def _agent():
    register_fixture_agent()
    yield
    unregister_fixture_agent()


def _pool(row):
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=row)
    acquire = MagicMock()
    acquire.__aenter__ = AsyncMock(return_value=conn)
    acquire.__aexit__ = AsyncMock(return_value=None)
    return SimpleNamespace(acquire=lambda: acquire)


def _make(plugin=None, *, row=None, execution=object()):
    plugin = plugin or FixturePlugin()
    app = FastAPI()
    app.state.container = SimpleNamespace(
        ui_manifest=collect_ui_contributions([plugin]),
        plugins=[plugin],
        pool=_pool(row or {"entity_type": "topic", "canonical_name": "climate"}),
        workflow_store=SimpleNamespace(get_execution=AsyncMock(return_value=execution)),
        settings=SimpleNamespace(ze_api_key=API_KEY),
    )
    app.state.settings = app.state.container.settings
    app.dependency_overrides[require_api_key] = lambda: None
    app.include_router(router, prefix="/api/v0")
    return plugin, app


async def _get(app, module_id, **params):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(
            f"/api/v0/ui/modules/{module_id}",
            params=params,
            headers={"Authorization": f"Bearer {API_KEY}"},
        )


ENTITY_Q = {"subject_kind": "entity", "subject_id": str(ENTITY)}


async def test_success_returns_tree_with_ui_version():
    _, app = _make()
    resp = await _get(app, "fixture_plugin.entity", **ENTITY_Q)
    assert resp.status_code == 200
    body = resp.json()
    assert body["module_id"] == "fixture_plugin.entity"
    assert body["applies"] is True
    assert body["ui_version"] == "2.0"
    assert body["components"][0]["type"] == "claim_list"


async def test_each_slot_resolves_its_subject():
    seen: dict[str, ModuleSubject] = {}
    plugin = FixturePlugin()

    def spy(name):
        async def provider(subject):
            seen[name] = subject
            return ModuleResult(applies=False)

        return provider

    plugin.providers = {
        "fixture_plugin.entity": spy("entity"),
        "fixture_plugin.run": spy("run"),
        "fixture_plugin.card": spy("card"),
    }
    _, app = _make(plugin)
    await _get(app, "fixture_plugin.entity", **ENTITY_Q)
    await _get(
        app,
        "fixture_plugin.run",
        subject_kind="workflow_run",
        subject_id=str(RUN),
        parent_id=str(WORKFLOW),
    )
    await _get(app, "fixture_plugin.card", subject_kind="none")
    assert seen["entity"] == ModuleSubject(
        kind="entity", id=str(ENTITY), label="climate", entity_type="topic"
    )
    assert seen["run"] == ModuleSubject(
        kind="workflow_run", id=str(RUN), parent_id=str(WORKFLOW)
    )
    assert seen["card"] == ModuleSubject(kind="none")


async def test_forged_label_in_query_is_ignored():
    seen = {}
    plugin = FixturePlugin()

    async def provider(subject):
        seen["subject"] = subject
        return ModuleResult(applies=False)

    plugin.providers["fixture_plugin.entity"] = provider
    _, app = _make(plugin)
    await _get(
        app,
        "fixture_plugin.entity",
        subject_label="forged",
        subject_entity_type="person",
        **ENTITY_Q,
    )
    assert seen["subject"].label == "climate"
    assert seen["subject"].entity_type == "topic"


async def test_not_applicable_passes_through():
    plugin = FixturePlugin()

    async def provider(subject):
        return ModuleResult(applies=False)

    plugin.providers["fixture_plugin.entity"] = provider
    _, app = _make(plugin)
    resp = await _get(app, "fixture_plugin.entity", **ENTITY_Q)
    assert resp.status_code == 200
    assert resp.json() == {
        "module_id": "fixture_plugin.entity",
        "applies": False,
        "components": [],
        "ui_version": "2.0",
    }


async def test_unknown_module_is_404():
    _, app = _make()
    assert (await _get(app, "nope", subject_kind="none")).status_code == 404


async def test_unknown_entity_is_404():
    _, app = _make()
    app.state.container.pool = _pool(None)
    assert (await _get(app, "fixture_plugin.entity", **ENTITY_Q)).status_code == 404


async def test_malformed_subject_id_is_404():
    _, app = _make()
    resp = await _get(
        app, "fixture_plugin.entity", subject_kind="entity", subject_id="not-a-uuid"
    )
    assert resp.status_code == 404


async def test_unknown_run_is_404():
    _, app = _make(execution=None)
    resp = await _get(
        app,
        "fixture_plugin.run",
        subject_kind="workflow_run",
        subject_id=str(RUN),
        parent_id=str(WORKFLOW),
    )
    assert resp.status_code == 404


async def test_subject_kind_not_valid_for_slot_is_422():
    _, app = _make()
    resp = await _get(app, "fixture_plugin.card", **ENTITY_Q)
    assert resp.status_code == 422


async def test_provider_error_is_502_and_logged():
    plugin = FixturePlugin()

    async def provider(subject):
        raise RuntimeError("boom")

    plugin.providers["fixture_plugin.entity"] = provider
    _, app = _make(plugin)
    with capture_logs() as logs:
        resp = await _get(app, "fixture_plugin.entity", **ENTITY_Q)
    assert resp.status_code == 502
    assert resp.json()["detail"] == "Fixture Plugin could not load."
    assert any(e["event"] == "ui_module_failed" for e in logs)


async def test_slow_provider_is_504(monkeypatch):
    monkeypatch.setattr(module_router, "PROVIDER_TIMEOUT_S", 0.01)
    plugin = FixturePlugin()

    async def provider(subject):
        await asyncio.sleep(1)
        return ModuleResult(applies=False)

    plugin.providers["fixture_plugin.entity"] = provider
    _, app = _make(plugin)
    with capture_logs() as logs:
        resp = await _get(app, "fixture_plugin.entity", **ENTITY_Q)
    assert resp.status_code == 504
    assert resp.json()["detail"] == "Fixture Plugin took too long."
    assert any(e["event"] == "ui_module_failed" for e in logs)


def _with_tree(tree):
    plugin = FixturePlugin()

    async def provider(subject):
        return ModuleResult(applies=True, components=tree)

    plugin.providers["fixture_plugin.entity"] = provider
    return _make(plugin)[1]


def _button(action):
    return [{"type": "button", "label": "Go", "action": action}]


@pytest.mark.parametrize(
    "tree",
    [
        [{"type": "nope"}],
        _button({"kind": "tool", "owner": "other", "tool": "wipe", "args": {}}),
        _button({"kind": "tool", "owner": "fixture", "tool": "wipe", "args": {}}),
        [
            {
                "type": "headline",
                "text": "X",
                "claim": {"kind": "priority", "subject": "fact", "ref_id": "1"},
            }
        ],
    ],
    ids=["unknown-primitive", "foreign-agent", "foreign-tool", "unlicensed-posture"],
)
async def test_invalid_tree_is_502(tree):
    app = _with_tree(tree)
    with capture_logs() as logs:
        resp = await _get(app, "fixture_plugin.entity", **ENTITY_Q)
    assert resp.status_code == 502
    assert resp.json()["detail"] == "Fixture Plugin sent a view Ze cannot show."
    assert any(e["event"] == "ui_module_failed" for e in logs)


async def test_own_agent_tool_action_passes():
    app = _with_tree(
        _button({"kind": "tool", "owner": "fixture", "tool": "save_note", "args": {}})
    )
    resp = await _get(app, "fixture_plugin.entity", **ENTITY_Q)
    assert resp.status_code == 200


async def test_provider_set_card_tone_is_replaced_by_core():
    card = {
        "type": "claim_card",
        "title": "Hot take",
        "claim": {
            "kind": "suspicion",
            "subject": "fact",
            "ref_id": "1",
            "source": "synthesized",
        },
        "tone": "hot",
    }
    app = _with_tree([card])
    resp = await _get(app, "fixture_plugin.entity", **ENTITY_Q)
    assert resp.status_code == 200
    assert resp.json()["components"][0]["tone"] == "dotted"
