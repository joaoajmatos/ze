from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from ze_agents.claims import ClaimKind
from ze_communication.registry import ChannelRegistry
from ze_communication.types import ChannelType, SentMessage
from ze_memory.action_records.types import ActionLifecycle
from ze_plugin.contribution import SourceFunction

from ze_messenger.outbound.adapter import (
    configure_outbound_ledger,
    contribution_from_outbound,
    record_outbound_message,
)
from ze_messenger.outbound.types import OutboundSend, OutboundSendOutcome


def _send(**overrides) -> OutboundSend:
    now = datetime.now(timezone.utc)
    base = dict(
        id=uuid4(),
        message_id="gmail-1",
        thread_id="thread-1",
        channel_type="email",
        channel_id="gmail:ze@example.com",
        sent_at=now,
        outcome=OutboundSendOutcome.SUCCESS,
    )
    base.update(overrides)
    return OutboundSend(**base)


def test_ledger_summary_omits_recipient_and_body() -> None:
    send = _send()
    draft = contribution_from_outbound(send).action_record
    assert send.channel_id not in draft.summary
    assert "secret" not in draft.summary
    assert draft.authoritative_ref.record_id == str(send.id)
    assert draft.authoritative_ref.domain == "messenger.outbound"


def test_outbound_contribution_is_action_record() -> None:
    contribution = contribution_from_outbound(_send())
    assert contribution.claim_kind is ClaimKind.ACTION_RECORD
    assert contribution.source_function is SourceFunction.ACTION


def test_failure_and_unknown_are_truthful() -> None:
    failed = contribution_from_outbound(
        _send(outcome=OutboundSendOutcome.FAILURE, failure_code="ChannelSendError")
    ).action_record
    unknown = contribution_from_outbound(
        _send(outcome=OutboundSendOutcome.UNKNOWN, failure_code="Timeout")
    ).action_record
    assert failed.lifecycle is ActionLifecycle.FAILED
    assert unknown.lifecycle is ActionLifecycle.UNKNOWN


async def test_record_outbound_duplicate_delivery() -> None:
    action_store = AsyncMock()
    action_store.get = AsyncMock(return_value=None)
    action_store.append = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    outbound_store = AsyncMock()
    configure_outbound_ledger(
        outbound_store=outbound_store, action_record_store=action_store
    )
    send = _send()
    await record_outbound_message(send)
    await record_outbound_message(send)
    assert action_store.append.await_count == 2


async def test_send_email_persists_source_then_ledger() -> None:
    from ze_messenger.agents.messenger import tools as messenger_tools

    sent = SentMessage(
        message_id="m1",
        thread_id="t1",
        channel_type=ChannelType.EMAIL,
        sent_at=datetime.now(timezone.utc),
    )
    channel = MagicMock()
    channel.channel_id = "gmail:ze@example.com"
    channel.channel_type = ChannelType.EMAIL
    channel.send = AsyncMock(return_value=sent)
    registry = MagicMock(spec=ChannelRegistry)
    thread_map = AsyncMock()
    thread_map.get = AsyncMock(return_value=None)
    thread_map.set = AsyncMock()
    user_channels = AsyncMock()
    user_channels.get_default_outbound = AsyncMock(return_value=None)
    registry.get_inbound_by_id = MagicMock(return_value=None)
    registry.inbound_channels = MagicMock(return_value=[channel])

    outbound_store = AsyncMock()
    persisted = _send()
    outbound_store.insert = AsyncMock(return_value=persisted)
    action_store = AsyncMock()
    action_store.get = AsyncMock(return_value=None)
    action_store.append = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    configure_outbound_ledger(
        outbound_store=outbound_store, action_record_store=action_store
    )

    result = await messenger_tools.send_email(
        channel_registry=registry,
        thread_channel_map=thread_map,
        user_channel_store=user_channels,
        to="a@b.com",
        subject="hi",
        body="secret body",
    )
    assert result["message_id"] == "m1"
    outbound_store.insert.assert_awaited()
    inserted = outbound_store.insert.await_args.args[0]
    assert inserted.message_id == "m1"
    assert getattr(inserted, "body", None) is None
    action_store.append.assert_awaited()


async def test_send_email_unknown_on_uncertain_failure() -> None:
    from ze_messenger.agents.messenger import tools as messenger_tools

    channel = MagicMock()
    channel.channel_id = "gmail:ze@example.com"
    channel.channel_type = ChannelType.EMAIL
    channel.send = AsyncMock(side_effect=TimeoutError("hang"))
    registry = MagicMock(spec=ChannelRegistry)
    thread_map = AsyncMock()
    thread_map.get = AsyncMock(return_value=None)
    user_channels = AsyncMock()
    user_channels.get_default_outbound = AsyncMock(return_value=None)
    registry.inbound_channels = MagicMock(return_value=[channel])

    outbound_store = AsyncMock()
    outbound_store.insert = AsyncMock(
        return_value=_send(outcome=OutboundSendOutcome.UNKNOWN)
    )
    action_store = AsyncMock()
    action_store.get = AsyncMock(return_value=None)
    action_store.append = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    configure_outbound_ledger(
        outbound_store=outbound_store, action_record_store=action_store
    )

    with pytest.raises(TimeoutError):
        await messenger_tools.send_email(
            channel_registry=registry,
            thread_channel_map=thread_map,
            user_channel_store=user_channels,
            to="a@b.com",
            subject="hi",
            body="secret body",
        )
    assert (
        outbound_store.insert.await_args.args[0].outcome is OutboundSendOutcome.UNKNOWN
    )
