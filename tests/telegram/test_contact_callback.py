from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from ze.contacts.types import Person
from ze.telegram.keyboards import contact_confirmation_keyboard


# ── keyboard ──────────────────────────────────────────────────────────────────

def test_contact_confirmation_keyboard_callback_data():
    pid = uuid4()
    kb = contact_confirmation_keyboard(pid)
    buttons = kb.inline_keyboard[0]
    assert len(buttons) == 2
    assert buttons[0].callback_data == f"contact:confirm:{pid}"
    assert buttons[1].callback_data == f"contact:dismiss:{pid}"


def test_contact_confirmation_keyboard_fits_telegram_limit():
    pid = uuid4()
    kb = contact_confirmation_keyboard(pid)
    for row in kb.inline_keyboard:
        for btn in row:
            assert len(btn.callback_data.encode()) <= 64


# ── ZeBot contact callback ────────────────────────────────────────────────────

def _make_bot(person_store):
    """Build a minimal ZeBot instance with only the fields contact callback needs."""
    from ze.telegram.bot import ZeBot
    bot = MagicMock()
    bot.send_message = AsyncMock()

    instance = object.__new__(ZeBot)
    instance._bot = bot
    instance._person_store = person_store
    return instance


def _make_query(data: str, chat_id: int = 1234):
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.message.edit_reply_markup = AsyncMock()
    query.message.chat.id = chat_id
    return query


async def test_confirm_callback_confirms_and_acks():
    pid = uuid4()
    person = Person(id=pid, name="João Silva", confirmed=False, dismissed=False, confidence=0.9)

    store = AsyncMock()
    store.confirm = AsyncMock(return_value=person)

    bot = _make_bot(store)
    query = _make_query(f"contact:confirm:{pid}")

    await bot._handle_contact_callback(1234, query)

    store.confirm.assert_awaited_once_with(pid)
    bot._bot.send_message.assert_awaited_once()
    text = bot._bot.send_message.call_args[0][1]
    assert "João Silva" in text


async def test_dismiss_callback_dismisses_silently():
    pid = uuid4()

    store = AsyncMock()
    store.dismiss = AsyncMock()

    bot = _make_bot(store)
    query = _make_query(f"contact:dismiss:{pid}")

    await bot._handle_contact_callback(1234, query)

    store.dismiss.assert_awaited_once_with(pid)
    bot._bot.send_message.assert_not_awaited()


async def test_confirm_callback_handles_not_found():
    pid = uuid4()

    store = AsyncMock()
    store.confirm = AsyncMock(side_effect=ValueError("not found"))

    bot = _make_bot(store)
    query = _make_query(f"contact:confirm:{pid}")

    await bot._handle_contact_callback(1234, query)

    bot._bot.send_message.assert_awaited_once()
    text = bot._bot.send_message.call_args[0][1]
    assert "not found" in text.lower()


async def test_invalid_uuid_is_ignored():
    store = AsyncMock()
    bot = _make_bot(store)
    query = _make_query("contact:confirm:not-a-uuid")

    await bot._handle_contact_callback(1234, query)

    store.confirm.assert_not_awaited()
    bot._bot.send_message.assert_not_awaited()


async def test_unknown_action_is_ignored():
    pid = uuid4()
    store = AsyncMock()
    bot = _make_bot(store)
    query = _make_query(f"contact:merge:{pid}")

    await bot._handle_contact_callback(1234, query)

    store.confirm.assert_not_awaited()
    store.dismiss.assert_not_awaited()
