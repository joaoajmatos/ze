from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze.telegram.bot import ZeBot
from ze_personal.goals.types import Goal, GoalStatus, GoalSuggestion, SuggestionStatus


# ── helpers ───────────────────────────────────────────────────────────────────

def _suggestion(status=SuggestionStatus.PENDING) -> GoalSuggestion:
    return GoalSuggestion(
        id=uuid4(),
        title="Learn Spanish",
        objective="Achieve conversational fluency within 6 months.",
        rationale="Based on your retrospective for 'Travel to South America' in 2024, language was the main barrier.",
        source_type="retrospective",
        source_ref="Travel to South America",
        status=status,
        suggested_at=datetime.now(timezone.utc),
    )


def _created_goal(suggestion: GoalSuggestion) -> Goal:
    return Goal(
        id=uuid4(),
        title=suggestion.title,
        objective=suggestion.objective,
        success_condition=suggestion.objective,
        status=GoalStatus.ACTIVE,
        type="suggested",
    )


def _make_query(data: str) -> MagicMock:
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.edit_reply_markup = AsyncMock()
    query.message.answer = AsyncMock()
    query.message.chat.id = 1234
    return query


_UNSET = object()


def _make_bot(
    *,
    suggestion: GoalSuggestion | None = None,
    resolve_returns=_UNSET,
    mark_accepted_returns=True,
    mark_dismissed_returns=True,
    create_goal_raises=False,
):
    bot_mock = MagicMock()
    bot_mock.send_message = AsyncMock()

    suggestion_store = AsyncMock()
    suggestion_store.resolve_short_id = AsyncMock(
        return_value=suggestion if resolve_returns is _UNSET else resolve_returns
    )
    suggestion_store.mark_accepted = AsyncMock(return_value=mark_accepted_returns)
    suggestion_store.mark_dismissed = AsyncMock(return_value=mark_dismissed_returns)

    goal_store = AsyncMock()
    if create_goal_raises:
        goal_store.create_goal = AsyncMock(side_effect=RuntimeError("DB error"))
    else:
        goal_store.create_goal = AsyncMock(
            return_value=_created_goal(suggestion) if suggestion else None
        )

    planner = MagicMock()
    planner.create_goal_from_suggestion = MagicMock(
        return_value=_created_goal(suggestion) if suggestion else None
    )

    executor = AsyncMock()
    executor.advance = AsyncMock(return_value=None)

    instance = object.__new__(ZeBot)
    instance._bot = bot_mock
    instance._goal_suggestion_store = suggestion_store
    instance._goal_store = goal_store
    instance._goal_planner = planner
    instance._goal_executor = executor

    return instance, suggestion_store, goal_store, planner, executor


# ── accept flow ───────────────────────────────────────────────────────────────

async def test_accept_creates_goal_and_removes_keyboard():
    s = _suggestion()
    bot, suggestion_store, goal_store, planner, executor = _make_bot(suggestion=s)

    query = _make_query(f"goal_suggest:accept:{s.id.hex[:8]}")
    await bot._handle_suggestion_callback(query, query.data)

    planner.create_goal_from_suggestion.assert_called_once_with(s)
    goal_store.create_goal.assert_called_once()
    suggestion_store.mark_accepted.assert_called_once()
    query.message.edit_reply_markup.assert_called_once_with(reply_markup=None)
    query.message.answer.assert_called_once()
    assert "Learn Spanish" in query.message.answer.call_args.args[0]


async def test_accept_starts_executor_advance():
    s = _suggestion()
    bot, _, _, _, executor = _make_bot(suggestion=s)

    query = _make_query(f"goal_suggest:accept:{s.id.hex[:8]}")
    await bot._handle_suggestion_callback(query, query.data)

    # Give the background task a chance to run
    await asyncio.sleep(0)
    executor.advance.assert_called_once()


async def test_accept_leaves_keyboard_intact_when_goal_creation_fails():
    s = _suggestion()
    bot, suggestion_store, _, _, _ = _make_bot(suggestion=s, create_goal_raises=True)

    query = _make_query(f"goal_suggest:accept:{s.id.hex[:8]}")
    await bot._handle_suggestion_callback(query, query.data)

    query.message.edit_reply_markup.assert_not_called()
    suggestion_store.mark_accepted.assert_not_called()
    query.message.answer.assert_called_once()
    assert "went wrong" in query.message.answer.call_args.args[0]


async def test_accept_is_idempotent_on_double_tap():
    s = _suggestion()
    bot, suggestion_store, _, _, _ = _make_bot(suggestion=s, mark_accepted_returns=False)

    query = _make_query(f"goal_suggest:accept:{s.id.hex[:8]}")
    await bot._handle_suggestion_callback(query, query.data)

    # When mark_accepted returns False: keyboard not removed, no confirmation message
    query.message.edit_reply_markup.assert_not_called()
    query.message.answer.assert_not_called()


async def test_accept_on_already_resolved_suggestion_answered_silently():
    s = _suggestion(status=SuggestionStatus.ACCEPTED)
    bot, _, _, _, _ = _make_bot(suggestion=s, resolve_returns=s)

    query = _make_query(f"goal_suggest:accept:{s.id.hex[:8]}")
    await bot._handle_suggestion_callback(query, query.data)

    query.answer.assert_called_once()
    assert "no longer active" in query.answer.call_args.args[0]
    query.message.edit_reply_markup.assert_not_called()


# ── dismiss flow ──────────────────────────────────────────────────────────────

async def test_dismiss_uses_atomic_conditional_update():
    s = _suggestion()
    bot, suggestion_store, _, _, _ = _make_bot(suggestion=s)

    query = _make_query(f"goal_suggest:dismiss:{s.id.hex[:8]}")
    await bot._handle_suggestion_callback(query, query.data)

    suggestion_store.mark_dismissed.assert_called_once_with(s.id)
    query.message.edit_reply_markup.assert_called_once_with(reply_markup=None)


async def test_dismiss_is_noop_if_accept_already_won():
    s = _suggestion()
    bot, suggestion_store, _, _, _ = _make_bot(suggestion=s, mark_dismissed_returns=False)

    query = _make_query(f"goal_suggest:dismiss:{s.id.hex[:8]}")
    await bot._handle_suggestion_callback(query, query.data)

    query.message.edit_reply_markup.assert_not_called()
    query.answer.assert_called()


# ── tell me more flow ─────────────────────────────────────────────────────────

async def test_tell_me_more_sends_expanded_message_no_llm_call():
    s = _suggestion()
    bot, _, _, planner, _ = _make_bot(suggestion=s)

    query = _make_query(f"goal_suggest:more:{s.id.hex[:8]}")
    await bot._handle_suggestion_callback(query, query.data)

    # No LLM call
    planner.create_goal_from_suggestion.assert_not_called()

    query.message.answer.assert_called_once()
    text = query.message.answer.call_args.args[0]
    kwargs = query.message.answer.call_args.kwargs
    assert "Learn Spanish" in text
    # Rationale and objective are HTML-escaped in the output
    assert "Travel to South America" in text
    assert "conversational fluency" in text
    assert kwargs.get("parse_mode") == "HTML"

    # New keyboard re-offers accept/dismiss
    keyboard = kwargs.get("reply_markup")
    assert keyboard is not None
    payloads = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
    short_id = s.id.hex[:8]
    assert f"goal_suggest:accept:{short_id}" in payloads
    assert f"goal_suggest:dismiss:{short_id}" in payloads


async def test_tell_me_more_leaves_original_keyboard_intact():
    s = _suggestion()
    bot, _, _, _, _ = _make_bot(suggestion=s)

    query = _make_query(f"goal_suggest:more:{s.id.hex[:8]}")
    await bot._handle_suggestion_callback(query, query.data)

    query.message.edit_reply_markup.assert_not_called()


# ── short ID not found ────────────────────────────────────────────────────────

async def test_unknown_short_id_answers_silently():
    s = _suggestion()
    bot, _, _, _, _ = _make_bot(suggestion=s, resolve_returns=None)

    query = _make_query("goal_suggest:accept:deadbeef")
    await bot._handle_suggestion_callback(query, query.data)

    query.answer.assert_called_once()
    # answer() may be called positionally or as a keyword arg
    call = query.answer.call_args
    text = call.args[0] if call.args else call.kwargs.get("text", "")
    assert "no longer active" in text
