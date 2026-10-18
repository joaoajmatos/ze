"""InboundPollingJob records each poll's outcome (phase 194, US5)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from google.auth.exceptions import RefreshError

from ze_communication.types import ChannelType
from ze_messenger.jobs import inbound_poll
from ze_messenger.jobs.inbound_poll import InboundPollingJob
from ze_personal.channels.types import PollOutcome, UserChannel


def _channel(channel_id="gmail:me@x", user_email="me@x", supports_push=False):
    ch = MagicMock()
    ch.channel_id = channel_id
    ch.channel_type = ChannelType.EMAIL
    ch.supports_push = supports_push
    ch._user_email = user_email
    ch.poll_new_messages = AsyncMock(return_value=[])
    ch._resolve_user_email = AsyncMock(return_value=user_email)
    return ch


def _job(channel, user_channels=()):
    registry = MagicMock()
    registry.inbound_channels.return_value = [channel]
    marks = AsyncMock()
    marks.get = AsyncMock(return_value=datetime.now(timezone.utc))
    users = AsyncMock()
    users.list_all = AsyncMock(return_value=list(user_channels))
    calls = MagicMock()
    calls.attach_mock(users.ensure, "ensure")
    calls.attach_mock(users.upsert, "upsert")
    calls.attach_mock(users.drop_unkeyed, "drop_unkeyed")
    calls.attach_mock(marks.record_outcome, "record_outcome")
    job = InboundPollingJob(
        registry=registry,
        watermark_store=marks,
        user_channel_store=users,
        processor=AsyncMock(),
    )
    return job, marks, users, calls


def _existing(channel_id="gmail:me@x", handle="me@x"):
    return UserChannel(
        id=uuid4(),
        channel_id=channel_id,
        channel_type="email",
        handle=handle,
        display_name=None,
        is_default_outbound=False,
        poll_enabled=True,
        created_at=datetime.now(timezone.utc),
    )


def _outcome(marks) -> PollOutcome:
    return marks.record_outcome.call_args[0][1]


async def test_successful_poll_records_ok():
    ch = _channel()
    job, marks, _, _ = _job(ch)

    await job.run()

    marks.record_outcome.assert_called_once()
    assert marks.record_outcome.call_args[0][0] == "gmail:me@x"
    assert _outcome(marks) is PollOutcome.OK


async def test_auth_failure_records_auth_failed_after_ensure_and_never_upserts():
    ch = _channel(channel_id="email", user_email=None)
    ch._resolve_user_email = AsyncMock(side_effect=RefreshError("invalid_grant"))
    job, marks, users, calls = _job(ch)

    await job.run()

    assert _outcome(marks) is PollOutcome.AUTH_FAILED
    names = [c[0] for c in calls.mock_calls]
    assert names.index("ensure") < names.index("record_outcome")
    users.upsert.assert_not_called()


async def test_failed_poll_keeps_the_known_handle():
    ch = _channel(channel_id="gmail:me@x", user_email=None)
    ch.poll_new_messages = AsyncMock(side_effect=RuntimeError("boom"))
    job, marks, users, _ = _job(ch, [_existing()])

    await job.run()

    users.upsert.assert_not_called()
    ensured = users.ensure.call_args[0][0]
    assert ensured.channel_id == "gmail:me@x"
    assert _outcome(marks) is PollOutcome.FAILED


async def test_unresolved_email_records_under_the_bare_key():
    ch = _channel(channel_id="email", user_email=None)
    ch._resolve_user_email = AsyncMock(side_effect=RefreshError("invalid_grant"))
    job, marks, users, _ = _job(ch)

    await job.run()

    assert marks.record_outcome.call_args[0][0] == "email"
    assert users.ensure.call_args[0][0].channel_id == "email"


async def test_keyed_success_drops_the_bare_key_rows():
    ch = _channel(channel_id="gmail:me@x")
    job, _, users, _ = _job(ch)

    await job.run()

    users.drop_unkeyed.assert_called_once_with("email")


async def test_success_under_the_bare_key_does_not_drop_it():
    ch = _channel(channel_id="email", user_email=None)
    job, _, users, _ = _job(ch)

    await job.run()

    users.drop_unkeyed.assert_not_called()


async def test_other_exceptions_record_failed():
    ch = _channel()
    ch.poll_new_messages = AsyncMock(side_effect=RuntimeError("network"))
    job, marks, _, _ = _job(ch, [_existing()])

    await job.run()

    assert _outcome(marks) is PollOutcome.FAILED


async def test_push_channels_record_nothing():
    ch = _channel(supports_push=True)
    job, marks, users, _ = _job(ch)

    await job.run()

    marks.record_outcome.assert_not_called()
    users.ensure.assert_not_called()


async def test_recording_failure_never_breaks_the_poll():
    ch = _channel()
    job, marks, _, _ = _job(ch)
    marks.record_outcome = AsyncMock(side_effect=RuntimeError("db down"))

    await job.run()  # must not raise

    marks.record_outcome.assert_called_once()


async def test_recording_failure_after_a_failed_poll_is_swallowed():
    ch = _channel()
    ch.poll_new_messages = AsyncMock(side_effect=RuntimeError("network"))
    job, marks, users, _ = _job(ch, [_existing()])
    users.ensure = AsyncMock(side_effect=RuntimeError("db down"))

    await job.run()  # must not raise


def test_plugin_does_not_import_google_auth():
    source = Path(inbound_poll.__file__).read_text()
    assert "google.auth" not in source
