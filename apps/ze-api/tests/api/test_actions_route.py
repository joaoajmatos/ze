"""Tests for GET /api/v0/actions (phase 194)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_agents.claims import Confidence, DecayProfile, Provenance
from ze_api.api.deps import get_action_record_store, require_api_key
from ze_api.api.v0.actions.router import router
from ze_memory.action_records.types import (
    ActionContext,
    ActionLifecycle,
    ActionOutcome,
    ActionRecord,
    ActionSubjectKind,
    AuthoritativeRef,
)
from ze_plugin.contribution import TargetFace

NOW = datetime(2026, 10, 18, 9, tzinfo=timezone.utc)


def _record(minutes: int = 0, **kw) -> ActionRecord:
    base = dict(
        id=uuid4(),
        idempotency_key=str(uuid4()),
        action_type="workflow.execute",
        actor="workflow_scheduler",
        producer_plugin="ze-automation",
        lifecycle=ActionLifecycle.FAILED,
        outcome=ActionOutcome.FAILURE,
        occurred_at=NOW.replace(minute=minutes),
        provenance=Provenance.PROMPT_SUPPLIED,
        confidence=Confidence(value=1.0, decay_profile=DecayProfile.TIME_LINEAR),
        target_face=TargetFace.WORLD,
        summary="workflow execution failed",
        authoritative_ref=AuthoritativeRef(
            domain="workflow_execution", record_id="abc"
        ),
        context=ActionContext(),
        evidence=[],
        causal_refs=[],
        retry_of=None,
        supersedes=None,
        failure_code="workflow_failed",
    )
    base.update(kw)
    return ActionRecord(**base)


class FakeStore:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls: list[dict] = []

    async def list_by_subject(self, **kwargs):
        self.calls.append(kwargs)
        return self.rows[: kwargs["limit"]]


def _client(store) -> AsyncClient:
    app = FastAPI()
    app.state.settings = SimpleNamespace(ze_api_key="secret")
    app.dependency_overrides[require_api_key] = lambda: None
    app.dependency_overrides[get_action_record_store] = lambda: store
    app.include_router(router, prefix="/api/v0")
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


@pytest.mark.parametrize(
    "subject_type,kind",
    [
        ("goal", ActionSubjectKind.GOAL),
        ("workflow", ActionSubjectKind.WORKFLOW),
        ("workflow_run", ActionSubjectKind.WORKFLOW_RUN),
        ("workspace_run", ActionSubjectKind.WORKSPACE_RUN),
    ],
)
async def test_subject_type_maps_to_store_call(subject_type, kind):
    store = FakeStore()
    sid = uuid4()
    async with _client(store) as c:
        r = await c.get(
            "/api/v0/actions",
            params={"subject_type": subject_type, "subject_id": str(sid)},
        )
    assert r.status_code == 200
    assert store.calls[0]["kind"] is kind
    assert store.calls[0]["subject_id"] == sid
    assert store.calls[0]["cursor"] is None


async def test_no_subject_lists_everything():
    store = FakeStore()
    async with _client(store) as c:
        r = await c.get("/api/v0/actions")
    assert r.status_code == 200
    assert store.calls[0]["kind"] is None and store.calls[0]["subject_id"] is None


@pytest.mark.parametrize(
    "params",
    [
        {"subject_type": "goal"},
        {"subject_id": str(uuid4())},
        {"cursor": "not-a-cursor"},
        {"limit": 201},
        {"limit": 0},
        {"subject_type": "bogus", "subject_id": str(uuid4())},
    ],
)
async def test_bad_input_is_422(params):
    async with _client(FakeStore()) as c:
        r = await c.get("/api/v0/actions", params=params)
    assert r.status_code == 422


async def test_empty_result():
    async with _client(FakeStore()) as c:
        r = await c.get("/api/v0/actions")
    assert r.json() == {"items": [], "next_cursor": None}


async def test_item_fields_match_contract():
    rec = _record()
    async with _client(FakeStore([rec])) as c:
        r = await c.get("/api/v0/actions")
    item = r.json()["items"][0]
    assert item == {
        "id": str(rec.id),
        "action_type": "workflow.execute",
        "actor": "workflow_scheduler",
        "producer_plugin": "ze-automation",
        "lifecycle": "failed",
        "outcome": "failure",
        "summary": "workflow execution failed",
        "touched": {"domain": "workflow_execution", "record_id": "abc"},
        "occurred_at": "2026-10-18T09:00:00Z",
        "failure_code": "workflow_failed",
    }


async def test_next_cursor_round_trips_and_ends():
    rows = [_record(30), _record(20), _record(10)]
    store = FakeStore(rows)
    async with _client(store) as c:
        first = (await c.get("/api/v0/actions", params={"limit": 2})).json()
        assert [i["id"] for i in first["items"]] == [str(rows[0].id), str(rows[1].id)]
        assert first["next_cursor"]
        assert store.calls[0]["limit"] == 3

        store.rows = rows[2:]
        last = (
            await c.get(
                "/api/v0/actions", params={"limit": 2, "cursor": first["next_cursor"]}
            )
        ).json()
    assert store.calls[1]["cursor"] == (rows[1].occurred_at, rows[1].id)
    assert last["next_cursor"] is None and len(last["items"]) == 1


async def test_since_is_passed_through():
    store = FakeStore()
    async with _client(store) as c:
        r = await c.get("/api/v0/actions", params={"since": "2026-10-01T00:00:00Z"})
    assert r.status_code == 200
    assert store.calls[0]["since"] == datetime(2026, 10, 1, tzinfo=timezone.utc)
