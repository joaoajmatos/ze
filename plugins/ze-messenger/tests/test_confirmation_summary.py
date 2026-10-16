"""archive_email's confirmation names the email, not its id (Phase 181, e2e finding 2)."""

from __future__ import annotations

from unittest.mock import MagicMock

from ze_messenger.agents.messenger.tools import _email_label


def _credentials(headers: list[dict]) -> MagicMock:
    credentials = MagicMock()
    messages = credentials.gmail.return_value.users.return_value.messages.return_value
    messages.get.return_value.execute.return_value = {"payload": {"headers": headers}}
    return credentials


async def test_an_email_is_named_by_subject_and_sender() -> None:
    credentials = _credentials(
        [
            {"name": "Subject", "value": "Invoice 42"},
            {"name": "From", "value": "Ana <ana@example.com>"},
        ]
    )

    summary = await _email_label({"message_id": "m1", "credentials": credentials})

    assert summary == '"Invoice 42" from Ana <ana@example.com>'


async def test_an_email_without_a_subject_has_no_summary() -> None:
    assert (
        await _email_label({"message_id": "m1", "credentials": _credentials([])})
        is None
    )
