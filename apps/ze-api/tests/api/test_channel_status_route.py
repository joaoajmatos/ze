"""GET /api/v0/channels/status (phase 194, US5)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.v0.channels import router as channels_module
from ze_communication.types import ChannelType
from ze_api.api.v0.channels.router import router
from ze_personal.channels.types import ChannelPollStatus, PollOutcome, UserChannel

API_KEY = "test-key"
AUTH = {"Authorization": f"Bearer {API_KEY}"}
SYNC = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)


def _user_channel(channel_id="gmail:me@x", handle="me@x", poll_enabled=True):
    return UserChannel(
        id=uuid4(),
        channel_id=channel_id,
        channel_type="email",
        handle=handle,
        display_name=None,
        is_default_outbound=False,
        poll_enabled=poll_enabled,
        created_at=SYNC,
    )


def _registry_channel(channel_id="gmail:me@x", supports_push=False):
    return SimpleNamespace(
        channel_id=channel_id,
        channel_type=ChannelType.EMAIL,
        supports_push=supports_push,
    )


def _status(outcome: PollOutcome | None, watermark=SYNC):
    return ChannelPollStatus(
        watermark=watermark if outcome else None,
        last_outcome=outcome,
        last_outcome_at=SYNC if outcome else None,
    )


def _client(
    *,
    user_channels=(),
    registry_channels=(),
    statuses=None,
    configured=True,
    monkeypatch=None,
) -> AsyncClient:
    app = FastAPI()
    users = AsyncMock()
    users.list_all = AsyncMock(return_value=list(user_channels))
    marks = AsyncMock()
    marks.get_status_many = AsyncMock(return_value=statuses or {})
    registry = MagicMock()
    registry.inbound_channels.return_value = list(registry_channels)
    app.state.container = SimpleNamespace(
        user_channel_store=users, watermark_store=marks, channel_registry=registry
    )
    app.state.settings = SimpleNamespace(ze_api_key=API_KEY)
    app.include_router(router, prefix="/api/v0")
    monkeypatch.setattr(
        channels_module,
        "get_google_settings",
        lambda: SimpleNamespace(
            google_client_id="id" if configured else "",
            google_client_secret="secret" if configured else "",
            google_refresh_token="refresh" if configured else "",
        ),
    )
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _fetch(client: AsyncClient) -> dict:
    async with client:
        resp = await client.get("/api/v0/channels/status", headers=AUTH)
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.parametrize(
    ("outcome", "state"),
    [
        (PollOutcome.OK, "connected"),
        (PollOutcome.AUTH_FAILED, "needs_reauth"),
        (PollOutcome.FAILED, "error"),
        (None, "unknown"),
    ],
)
async def test_state_mapping(monkeypatch, outcome, state):
    client = _client(
        user_channels=[_user_channel()],
        registry_channels=[_registry_channel()],
        statuses={"gmail:me@x": _status(outcome)},
        monkeypatch=monkeypatch,
    )
    body = await _fetch(client)
    assert body["channels"][0]["state"] == state


async def test_poll_disabled_is_off(monkeypatch):
    client = _client(
        user_channels=[_user_channel(poll_enabled=False)],
        registry_channels=[_registry_channel()],
        statuses={"gmail:me@x": _status(PollOutcome.OK)},
        monkeypatch=monkeypatch,
    )
    assert (await _fetch(client))["channels"][0]["state"] == "off"


async def test_push_channel_is_unknown_even_after_an_ok_outcome(monkeypatch):
    client = _client(
        user_channels=[_user_channel()],
        registry_channels=[_registry_channel(supports_push=True)],
        statuses={"gmail:me@x": _status(PollOutcome.OK)},
        monkeypatch=monkeypatch,
    )
    item = (await _fetch(client))["channels"][0]
    assert item["state"] == "unknown"
    assert item["push"] is True


async def test_last_sync_is_the_watermark_only_after_ok(monkeypatch):
    ok = _client(
        user_channels=[_user_channel()],
        registry_channels=[_registry_channel()],
        statuses={"gmail:me@x": _status(PollOutcome.OK)},
        monkeypatch=monkeypatch,
    )
    assert (await _fetch(ok))["channels"][0][
        "last_sync_at"
    ] == SYNC.isoformat().replace("+00:00", "Z")
    failed = _client(
        user_channels=[_user_channel()],
        registry_channels=[_registry_channel()],
        statuses={"gmail:me@x": _status(PollOutcome.FAILED)},
        monkeypatch=monkeypatch,
    )
    assert (await _fetch(failed))["channels"][0]["last_sync_at"] is None


async def test_registry_channel_missing_from_user_channels_is_listed(monkeypatch):
    client = _client(
        registry_channels=[_registry_channel("gmail:new@x")],
        monkeypatch=monkeypatch,
    )
    item = (await _fetch(client))["channels"][0]
    assert item["channel_id"] == "gmail:new@x"
    assert item["handle"] is None
    assert item["state"] == "unknown"
    assert item["last_sync_at"] is None


async def test_channel_listed_once_when_in_both(monkeypatch):
    client = _client(
        user_channels=[_user_channel()],
        registry_channels=[_registry_channel()],
        monkeypatch=monkeypatch,
    )
    assert len((await _fetch(client))["channels"]) == 1


async def test_google_configured_false_without_credentials(monkeypatch):
    client = _client(configured=False, monkeypatch=monkeypatch)
    assert (await _fetch(client))["google_configured"] is False


async def test_google_configured_true_with_credentials(monkeypatch):
    client = _client(configured=True, monkeypatch=monkeypatch)
    assert (await _fetch(client))["google_configured"] is True


async def test_response_carries_no_token_or_secret(monkeypatch):
    client = _client(
        user_channels=[_user_channel()],
        registry_channels=[_registry_channel()],
        statuses={"gmail:me@x": _status(PollOutcome.OK)},
        monkeypatch=monkeypatch,
    )
    text = str(await _fetch(client)).lower()
    for word in ("token", "secret", "refresh"):
        assert word not in text


async def test_requires_auth(monkeypatch):
    client = _client(monkeypatch=monkeypatch)
    async with client:
        resp = await client.get("/api/v0/channels/status")
    assert resp.status_code == 401
