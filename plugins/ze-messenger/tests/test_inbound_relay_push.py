"""T023 regression: the inbound relay must send through the governor.

Before phase 177, ``InboundMessageProcessor.process`` called
``ProactiveNotifier.push(title=…, body=…, tags=…)``. ``push`` takes
``(content, *, format, urgency)``, so the call raised and the "message from a
known contact" push never delivered. The fake notifier here exposes only
``notify``, so any lingering ``push(...)`` call fails loudly.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from ze_communication.types import ChannelType, InboundMessage
from ze_messenger.inbound.processor import InboundMessageProcessor
from ze_messenger.push_kinds import INBOUND_MESSAGE
from ze_messenger.signals import MessagingSignalSource
from ze_sdk.proactive import OncePer


def _msg(
    sender: str = "alice@example.com",
    subject: str = "Hello",
    body: str = "Hi there",
    message_id: str = "msg1",
) -> InboundMessage:
    return InboundMessage(
        message_id=message_id,
        channel_type=ChannelType.EMAIL,
        sender=sender,
        subject=subject,
        body=body,
        thread_id="t1",
        received_at=datetime(2026, 6, 26, 10, 0, tzinfo=timezone.utc),
        headers={},
    )


def _contact(name: str = "Alice") -> MagicMock:
    contact = MagicMock()
    contact.name = name
    return contact


def _make_processor(*, contact) -> tuple[InboundMessageProcessor, SimpleNamespace]:
    memory = AsyncMock()
    contacts = AsyncMock()
    contacts.find_by_handle = AsyncMock(return_value=contact)
    thread_map = AsyncMock()
    thread_map.get = AsyncMock(return_value=None)
    thread_map.set = AsyncMock()
    embedder = MagicMock()
    embedder.encode_passage = embedder.encode_query = MagicMock(return_value=[0.1] * 10)

    # Only `notify`: a lingering `push(...)` call must raise AttributeError.
    notifier = SimpleNamespace(notify=AsyncMock(return_value="delivered"))

    processor = InboundMessageProcessor(
        memory_store=memory,
        contact_channel_store=contacts,
        thread_channel_map=thread_map,
        notifier=notifier,
        signal_source=MessagingSignalSource(),
        embedder=embedder,
        automated_sender_patterns=[],
        llm_client=None,
    )
    return processor, notifier


async def test_known_contact_relay_goes_through_notify():
    processor, notifier = _make_processor(contact=_contact("Alice"))

    await processor.process(_msg(), channel_id="gmail:ze@example.com")

    notifier.notify.assert_awaited_once()
    call = notifier.notify.call_args
    assert call.args[0] is INBOUND_MESSAGE
    assert "Alice" in call.args[1]
    assert call.kwargs["once_per"] == OncePer("inbound:email:msg1")


async def test_unknown_sender_relay_sends_nothing():
    processor, notifier = _make_processor(contact=None)

    await processor.process(
        _msg(sender="stranger@example.com"), channel_id="gmail:ze@example.com"
    )

    notifier.notify.assert_not_awaited()
