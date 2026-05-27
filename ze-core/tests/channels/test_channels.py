"""Tests for Channel ABC, ChannelRegistry, and channel types."""
import pytest

from ze_core.channels import Channel, ChannelRegistry
from ze_core.channels.types import ChannelHandle, Message, SentMessage, Thread, ThreadMessage
from ze_core.errors import ChannelError, ChannelNotFoundError


# ── stub implementation ───────────────────────────────────────────────────────

class StubChannel(Channel):
    channel_type = "stub"

    def __init__(self):
        self._sent = []

    async def send(self, message: Message) -> SentMessage:
        self._sent.append(message)
        return SentMessage(message_id="msg-1", channel_type=self.channel_type, recipient=message.recipient)

    async def get_thread(self, thread_id: str) -> Thread:
        return Thread(thread_id=thread_id, channel_type=self.channel_type)

    async def poll_replies(self, sent: SentMessage) -> list[Thread]:
        return []


# ── TestChannelTypes ──────────────────────────────────────────────────────────

class TestChannelTypes:
    def test_message_defaults(self):
        m = Message(content="hello", channel_type="email", recipient="a@b.com")
        assert m.metadata == {}

    def test_sent_message_fields(self):
        s = SentMessage(message_id="x", channel_type="sms", recipient="+1234")
        assert s.message_id == "x"

    def test_thread_message_fields(self):
        tm = ThreadMessage(message_id="m", sender="alice", content="hi", timestamp="2024-01-01")
        assert tm.content == "hi"

    def test_thread_defaults(self):
        t = Thread(thread_id="t1", channel_type="slack")
        assert t.messages == []

    def test_channel_handle(self):
        h = ChannelHandle(channel_type="email", address="user@example.com")
        assert h.channel_type == "email"


# ── TestChannelABC ────────────────────────────────────────────────────────────

class TestChannelABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            Channel()  # type: ignore[abstract]

    def test_stub_is_channel_instance(self):
        assert isinstance(StubChannel(), Channel)

    async def test_stub_send_returns_sent_message(self):
        ch = StubChannel()
        msg = Message(content="test", channel_type="stub", recipient="bob")
        sent = await ch.send(msg)
        assert isinstance(sent, SentMessage)
        assert sent.channel_type == "stub"

    async def test_stub_get_thread_returns_thread(self):
        ch = StubChannel()
        thread = await ch.get_thread("thread-1")
        assert thread.thread_id == "thread-1"

    async def test_stub_poll_replies_returns_list(self):
        ch = StubChannel()
        sent = SentMessage(message_id="m", channel_type="stub", recipient="x")
        replies = await ch.poll_replies(sent)
        assert replies == []


# ── TestChannelRegistry ───────────────────────────────────────────────────────

class TestChannelRegistry:
    def test_register_and_get(self):
        reg = ChannelRegistry()
        ch = StubChannel()
        reg.register(ch)
        assert reg.get("stub") is ch

    def test_get_unknown_raises(self):
        reg = ChannelRegistry()
        with pytest.raises(ChannelNotFoundError):
            reg.get("unknown")

    def test_channel_not_found_is_channel_error(self):
        reg = ChannelRegistry()
        with pytest.raises(ChannelError):
            reg.get("missing")

    def test_contains(self):
        reg = ChannelRegistry()
        reg.register(StubChannel())
        assert "stub" in reg
        assert "other" not in reg

    def test_all_returns_all_channels(self):
        reg = ChannelRegistry()
        ch = StubChannel()
        reg.register(ch)
        assert ch in reg.all()

    def test_register_overwrites_same_type(self):
        reg = ChannelRegistry()
        ch1 = StubChannel()
        ch2 = StubChannel()
        reg.register(ch1)
        reg.register(ch2)
        assert reg.get("stub") is ch2
        assert len(reg.all()) == 1

    def test_empty_registry_all(self):
        reg = ChannelRegistry()
        assert reg.all() == []
