"""PUT/GET message feedback (Phase 165 US1/US2)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_agents.errors import FeedbackRecordIdempotencyConflictError
from ze_api.api.deps import (
    get_confirmation_store,
    get_connection_manager,
    get_feedback_store,
    get_message_store,
    get_turn_lock,
    require_api_key,
)
from ze_api.api.v0.messages.router import router
from ze_core.conversation.messages.types import Message, MessageTrace
from ze_memory.feedback_records import FeedbackKind, FeedbackRecord
from ze_agents.claims import Confidence, DecayProfile, Provenance
from ze_plugin.contribution import TargetFace


def _msg(role="assistant", thread="t1", **kw) -> Message:
    return Message(
        id=kw.pop("id", uuid4()),
        role=role,
        text="hi",
        components=[],
        read=True,
        created_at=datetime.now(timezone.utc),
        thread_id=thread,
        **kw,
    )


def _trace() -> MessageTrace:
    return MessageTrace(
        agent="research",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.1,
        is_compound=False,
        subtasks=[],
        effects_known=True,
    )


def _rec(message_id, kind, t=0) -> FeedbackRecord:
    return FeedbackRecord(
        id=uuid4(),
        idempotency_key=str(uuid4()),
        message_id=message_id,
        thread_id="t1",
        kind=kind,
        occurred_at=datetime.fromtimestamp(1_800_000_000 + t, timezone.utc),
        provenance=Provenance.PROMPT_SUPPLIED,
        confidence=Confidence(1.0, DecayProfile.TIME_LINEAR),
        target_face=TargetFace.WORLD,
        trace_present=True,
    )


class _Env:
    def __init__(self, message: Message | None, trace=None, history=None):
        self.msgs = AsyncMock()
        self.msgs.get_message = AsyncMock(return_value=message)
        self.msgs.get_trace = AsyncMock(return_value=trace)
        self.msgs.latest_assistant_id = AsyncMock(
            return_value=message.id if message else None
        )
        by_id = {message.id: message} if message else {}
        self.msgs.get_messages = AsyncMock(return_value=by_id)
        self.msgs.get_traces = AsyncMock(
            return_value={message.id: trace} if message and trace else {}
        )
        self.history = list(history or [])
        self.fb = AsyncMock()
        self.fb.history = AsyncMock(side_effect=lambda mid: list(self.history))
        self.fb.list_for_messages = AsyncMock(
            side_effect=lambda ids: {i: list(self.history) for i in ids if self.history}
        )
        self.appended: list = []

        async def append(contribution):
            draft = contribution.feedback_record
            self.appended.append(draft)
            rec = _rec(draft.message_id, draft.kind, t=len(self.history) + 1)
            self.history.append(rec)
            return rec

        self.fb.append = AsyncMock(side_effect=append)
        self.conn = MagicMock()
        self.conn.is_busy = MagicMock(return_value=False)
        self.lock = MagicMock()
        self.lock.is_locked = MagicMock(return_value=False)
        self.conf = AsyncMock()
        self.conf.get_pending_for_thread = AsyncMock(return_value=[])

    def client(self) -> AsyncClient:
        app = FastAPI()
        app.dependency_overrides[require_api_key] = lambda: None
        app.dependency_overrides[get_message_store] = lambda: self.msgs
        app.dependency_overrides[get_feedback_store] = lambda: self.fb
        app.dependency_overrides[get_connection_manager] = lambda: self.conn
        app.dependency_overrides[get_turn_lock] = lambda: self.lock
        app.dependency_overrides[get_confirmation_store] = lambda: self.conf
        app.include_router(router, prefix="/api/v0")
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _put(env, mid, rating, key="k1"):
    async with env.client() as c:
        return await c.put(
            f"/api/v0/messages/{mid}/feedback",
            json={"rating": rating, "idempotency_key": key},
        )


@pytest.mark.asyncio
async def test_set_thumb_appends_one_record_and_returns_view():
    m = _msg()
    env = _Env(m, _trace())
    resp = await _put(env, m.id, "down")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current"] == "down"
    assert body["trace_present"] is True
    assert [h["kind"] for h in body["history"]] == ["thumbs_down"]
    assert body["retry"]["available"] is True
    draft = env.appended[0]
    assert draft.kind is FeedbackKind.THUMBS_DOWN
    assert draft.idempotency_key == f"feedback:{m.id}:k1"
    assert draft.trace_present is True


@pytest.mark.asyncio
async def test_change_keeps_history():
    m = _msg()
    env = _Env(m, _trace(), [_rec(m.id, FeedbackKind.THUMBS_UP)])
    body = (await _put(env, m.id, "down", "k2")).json()
    assert body["current"] == "down"
    assert [h["kind"] for h in body["history"]] == ["thumbs_up", "thumbs_down"]


@pytest.mark.asyncio
async def test_clear_appends_cleared_record():
    m = _msg()
    env = _Env(m, _trace(), [_rec(m.id, FeedbackKind.THUMBS_UP)])
    body = (await _put(env, m.id, "none", "k2")).json()
    assert body["current"] is None
    assert body["history"][-1]["kind"] == "cleared"


@pytest.mark.asyncio
async def test_none_on_unrated_is_noop():
    m = _msg()
    env = _Env(m, _trace())
    resp = await _put(env, m.id, "none")
    assert resp.status_code == 200
    assert env.appended == []


@pytest.mark.asyncio
async def test_same_rating_again_is_noop():
    m = _msg()
    env = _Env(m, _trace(), [_rec(m.id, FeedbackKind.THUMBS_UP)])
    await _put(env, m.id, "up", "k9")
    assert env.appended == []


@pytest.mark.asyncio
async def test_message_without_trace_is_rated_with_trace_present_false():
    m = _msg()
    env = _Env(m, None)
    body = (await _put(env, m.id, "up")).json()
    assert body["trace_present"] is False
    assert env.appended[0].trace_present is False
    assert body["retry"]["reason_code"] == "trace_unavailable"


@pytest.mark.asyncio
async def test_user_message_is_404():
    m = _msg(role="user")
    env = _Env(m)
    assert (await _put(env, m.id, "up")).status_code == 404
    assert env.appended == []


@pytest.mark.asyncio
async def test_unknown_message_is_404():
    env = _Env(None)
    assert (await _put(env, uuid4(), "up")).status_code == 404


@pytest.mark.asyncio
async def test_bad_rating_is_422():
    m = _msg()
    env = _Env(m)
    assert (await _put(env, m.id, "love")).status_code == 422


@pytest.mark.asyncio
async def test_idempotency_conflict_is_409():
    m = _msg()
    env = _Env(m, _trace())
    env.fb.append = AsyncMock(
        side_effect=FeedbackRecordIdempotencyConflictError("different")
    )
    assert (await _put(env, m.id, "up")).status_code == 409


@pytest.mark.asyncio
async def test_batch_get_omits_user_messages_and_reports_links():
    m = _msg(replaces=uuid4())
    u = _msg(role="user")
    env = _Env(m, _trace(), [_rec(m.id, FeedbackKind.THUMBS_DOWN)])
    env.msgs.get_messages = AsyncMock(return_value={m.id: m, u.id: u})
    async with env.client() as c:
        resp = await c.get(
            "/api/v0/messages/feedback",
            params={"ids": [str(m.id), str(u.id), str(uuid4())]},
        )
    items = resp.json()["items"]
    assert [i["message_id"] for i in items] == [str(m.id)]
    assert items[0]["current"] == "down"
    assert items[0]["replaces"] == str(m.replaces)
    assert items[0]["replaced_by"] is None


@pytest.mark.asyncio
async def test_batch_get_empty_ids():
    env = _Env(_msg())
    async with env.client() as c:
        resp = await c.get("/api/v0/messages/feedback")
    assert resp.json() == {"items": []}


@pytest.mark.asyncio
async def test_batch_reports_busy_and_pending():
    m = _msg()
    env = _Env(m, _trace())
    env.conn.is_busy = MagicMock(return_value=True)
    async with env.client() as c:
        busy = (
            await c.get("/api/v0/messages/feedback", params={"ids": str(m.id)})
        ).json()
    assert busy["items"][0]["retry"]["reason_code"] == "busy"
    env.conn.is_busy = MagicMock(return_value=False)
    env.conf.get_pending_for_thread = AsyncMock(return_value=[{"request_id": "r"}])
    async with env.client() as c:
        pend = (
            await c.get("/api/v0/messages/feedback", params={"ids": str(m.id)})
        ).json()
    assert pend["items"][0]["retry"]["reason_code"] == "turn_pending"
