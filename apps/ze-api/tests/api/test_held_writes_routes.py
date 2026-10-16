"""Held-write REST routes (Phase 181, contracts/rest.md)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.deps import require_api_key
from ze_api.api.routes.held_writes import router
from ze_automation.holds.resumer import HeldWriteResumer
from ze_automation.holds.types import HeldWrite, HeldWriteStatus


class MemoryStore:
    def __init__(self, *holds: HeldWrite) -> None:
        self.rows = {h.request_id: h for h in holds}

    async def get(self, request_id):
        return self.rows.get(request_id)

    async def list(self, status):
        return [h for h in self.rows.values() if h.status is status]

    async def decide(self, request_id, status):
        row = self.rows.get(request_id)
        if row is None or row.status is not HeldWriteStatus.OPEN:
            return False
        row.status = status
        return True


def _hold(request_id: str = "r1", **kw) -> HeldWrite:
    base = dict(
        request_id=request_id,
        source="workflow",
        owner_ref="exec-1",
        items=[
            {
                "item_id": "i1",
                "agent": "calendar",
                "tool": "delete_event",
                "effect_phrase": "delete a calendar event",
                "summary": "Dentist",
                "editable_field": None,
            },
            {
                "item_id": "i2",
                "agent": "messenger",
                "tool": "send_email",
                "effect_phrase": "send an email",
                "summary": "to: a@b.io",
                "editable_field": "body",
                "proposed_text": "hi",
            },
        ],
        payload={"source_name": "Weekly summary"},
        expires_at=datetime.now(tz=timezone.utc) + timedelta(hours=24),
        created_at=datetime.now(tz=timezone.utc),
    )
    base.update(kw)
    return HeldWrite(**base)


def _app(*holds: HeldWrite):
    store = MemoryStore(*holds)
    run = AsyncMock()
    resumer = HeldWriteResumer(store, resume_workflow=run)  # type: ignore[arg-type]
    connection_manager = SimpleNamespace(send_frame=AsyncMock())
    app = FastAPI()
    app.state.container = SimpleNamespace(
        held_write_store=store,
        held_write_resumer=resumer,
        connection_manager=connection_manager,
    )
    app.dependency_overrides[require_api_key] = lambda: None
    app.include_router(router, prefix="/api/v0")
    return app, store, run, connection_manager


async def _call(app, method: str, url: str, **kw):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.request(method, url, **kw)


@pytest.mark.asyncio
async def test_list_returns_open_holds_by_default() -> None:
    app, *_ = _app(_hold("open"), _hold("done", status=HeldWriteStatus.APPROVED))
    resp = await _call(app, "GET", "/api/v0/held-writes")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [i["request_id"] for i in items] == ["open"]
    assert items[0]["source_name"] == "Weekly summary"
    assert items[0]["items"][0]["effect_phrase"] == "delete a calendar event"


@pytest.mark.asyncio
async def test_list_can_filter_by_status() -> None:
    app, *_ = _app(_hold("done", status=HeldWriteStatus.DENIED))
    resp = await _call(app, "GET", "/api/v0/held-writes?status=denied")
    assert [i["request_id"] for i in resp.json()["items"]] == ["done"]


@pytest.mark.asyncio
async def test_unknown_id_is_404() -> None:
    app, *_ = _app()
    resp = await _call(
        app, "POST", "/api/v0/held-writes/nope/decision", json={"choice": "approve"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_a_decided_hold_is_409() -> None:
    app, *_ = _app(_hold("r1", status=HeldWriteStatus.APPROVED))
    resp = await _call(
        app, "POST", "/api/v0/held-writes/r1/decision", json={"choice": "deny"}
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_approve_claims_the_hold_and_resumes_the_run(monkeypatch) -> None:
    import asyncio

    app, store, run, conn = _app(_hold("r1"))
    resp = await _call(
        app,
        "POST",
        "/api/v0/held-writes/r1/decision",
        json={"choice": "approve", "edits": {"i2": "new body"}},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert store.rows["r1"].status is HeldWriteStatus.APPROVED
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    run.assert_awaited_once()
    hold, choice, edits = run.await_args.args
    assert (hold.request_id, choice, edits) == ("r1", "approve", {"i2": "new body"})
    conn.send_frame.assert_awaited_with({"type": "confirm_cancel", "id": "r1"})


@pytest.mark.asyncio
async def test_deny_resumes_with_a_deny_and_a_second_answer_is_409() -> None:
    import asyncio

    app, store, run, _ = _app(_hold("r1"))
    first = await _call(
        app, "POST", "/api/v0/held-writes/r1/decision", json={"choice": "deny"}
    )
    assert first.status_code == 200 and first.json()["status"] == "denied"
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert run.await_args.args[1] == "deny"
    second = await _call(
        app, "POST", "/api/v0/held-writes/r1/decision", json={"choice": "approve"}
    )
    assert second.status_code == 409
    assert run.await_count == 1


@pytest.mark.asyncio
async def test_an_edit_for_a_non_editable_item_is_rejected_and_nothing_resumes() -> (
    None
):
    app, store, run, _ = _app(_hold("r1"))
    resp = await _call(
        app,
        "POST",
        "/api/v0/held-writes/r1/decision",
        json={"choice": "approve", "edits": {"i1": "x"}},
    )
    assert resp.status_code == 422
    assert store.rows["r1"].status is HeldWriteStatus.OPEN
    run.assert_not_awaited()
