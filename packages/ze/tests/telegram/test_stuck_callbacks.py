from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze.telegram.bot import ZeBot
from ze_personal.goals.types import (
    GateStatus,
    Goal,
    GoalStatus,
    VerificationGate,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _goal(status: GoalStatus = GoalStatus.ACTIVE) -> Goal:
    return Goal(
        id=uuid4(),
        title="Learn Rust",
        objective="Build a CLI tool",
        success_condition="Tool works",
        status=status,
    )


def _gate(goal: Goal) -> VerificationGate:
    return VerificationGate(
        id=uuid4(),
        goal_id=goal.id,
        after_sequence=2,
        title="Mid-point review",
        status=GateStatus.PENDING,
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


def _make_bot(*, goal: Goal | None = None, gate: VerificationGate | None = None):
    bot_mock = MagicMock()
    bot_mock.send_message = AsyncMock()

    goal_store = AsyncMock()
    goal_store.get_goal = AsyncMock(return_value=goal)
    goal_store.get_pending_gate = AsyncMock(return_value=gate)
    goal_store.update_status = AsyncMock()

    executor = AsyncMock()
    executor.handle_gate_approved = AsyncMock(return_value=None)
    executor.handle_gate_stopped = AsyncMock(return_value=None)

    instance = object.__new__(ZeBot)
    instance._bot = bot_mock
    instance._goal_store = goal_store
    instance._goal_executor = executor
    instance._store = MagicMock()

    return instance, goal_store, executor


# ── dispatch ──────────────────────────────────────────────────────────────────

async def test_invalid_uuid_hex_answers_with_error():
    g = _goal()
    bot, _, _ = _make_bot(goal=g)
    query = _make_query("goal_stuck:pause:not-a-uuid")
    await bot._handle_stuck_callback(query, query.data)
    query.answer.assert_called_once_with("Invalid goal reference.")


async def test_nonexistent_goal_answers_with_error():
    bot, goal_store, _ = _make_bot(goal=None)
    query = _make_query(f"goal_stuck:pause:{uuid4().hex}")
    await bot._handle_stuck_callback(query, query.data)
    query.answer.assert_called_once_with("Goal not found.")


async def test_malformed_data_no_crash():
    bot, _, _ = _make_bot(goal=_goal())
    query = _make_query("goal_stuck:only_two_parts")
    await bot._handle_stuck_callback(query, query.data)
    query.answer.assert_called_once()


# ── pause ─────────────────────────────────────────────────────────────────────

async def test_pause_updates_status_and_removes_keyboard():
    g = _goal(GoalStatus.ACTIVE)
    bot, goal_store, _ = _make_bot(goal=g)
    query = _make_query(f"goal_stuck:pause:{g.id.hex}")
    await bot._handle_stuck_callback(query, query.data)
    goal_store.update_status.assert_called_once_with(g.id, GoalStatus.PAUSED)
    query.message.edit_reply_markup.assert_called_once_with(reply_markup=None)
    query.message.answer.assert_called_once()


async def test_pause_noop_if_already_resolved():
    g = _goal(GoalStatus.COMPLETED)
    bot, goal_store, _ = _make_bot(goal=g)
    query = _make_query(f"goal_stuck:pause:{g.id.hex}")
    await bot._handle_stuck_callback(query, query.data)
    goal_store.update_status.assert_not_called()
    query.message.edit_reply_markup.assert_not_called()


# ── abandon ───────────────────────────────────────────────────────────────────

async def test_abandon_updates_status_and_removes_keyboard():
    g = _goal(GoalStatus.ACTIVE)
    bot, goal_store, _ = _make_bot(goal=g)
    query = _make_query(f"goal_stuck:abandon:{g.id.hex}")
    await bot._handle_stuck_callback(query, query.data)
    goal_store.update_status.assert_called_once_with(g.id, GoalStatus.ABANDONED)
    query.message.edit_reply_markup.assert_called_once_with(reply_markup=None)


async def test_abandon_noop_if_already_abandoned():
    g = _goal(GoalStatus.ABANDONED)
    bot, goal_store, _ = _make_bot(goal=g)
    query = _make_query(f"goal_stuck:abandon:{g.id.hex}")
    await bot._handle_stuck_callback(query, query.data)
    goal_store.update_status.assert_not_called()


# ── redirect ──────────────────────────────────────────────────────────────────

async def test_redirect_removes_keyboard_and_sends_prompt():
    g = _goal()
    bot, _, _ = _make_bot(goal=g)
    query = _make_query(f"goal_stuck:redirect:{g.id.hex}")
    await bot._handle_stuck_callback(query, query.data)
    query.message.edit_reply_markup.assert_called_once_with(reply_markup=None)
    query.message.answer.assert_called_once()
    assert "Learn Rust" in query.message.answer.call_args.args[0]


# ── gate_approve ──────────────────────────────────────────────────────────────

async def test_gate_approve_calls_handle_gate_approved_and_removes_keyboard():
    import asyncio
    g = _goal(GoalStatus.AWAITING_GATE)
    gate = _gate(g)
    bot, _, executor = _make_bot(goal=g, gate=gate)
    query = _make_query(f"goal_stuck:gate_approve:{g.id.hex}")
    await bot._handle_stuck_callback(query, query.data)
    await asyncio.sleep(0)  # let background task run
    executor.handle_gate_approved.assert_called_once_with(gate.id)
    query.message.edit_reply_markup.assert_called_once_with(reply_markup=None)
    query.message.answer.assert_called_once()


async def test_gate_approve_noop_if_no_pending_gate():
    g = _goal(GoalStatus.AWAITING_GATE)
    bot, _, executor = _make_bot(goal=g, gate=None)
    query = _make_query(f"goal_stuck:gate_approve:{g.id.hex}")
    await bot._handle_stuck_callback(query, query.data)
    executor.handle_gate_approved.assert_not_called()


# ── gate_stop ─────────────────────────────────────────────────────────────────

async def test_gate_stop_calls_handle_gate_stopped_and_removes_keyboard():
    import asyncio
    g = _goal(GoalStatus.AWAITING_GATE)
    gate = _gate(g)
    bot, _, executor = _make_bot(goal=g, gate=gate)
    query = _make_query(f"goal_stuck:gate_stop:{g.id.hex}")
    await bot._handle_stuck_callback(query, query.data)
    await asyncio.sleep(0)
    executor.handle_gate_stopped.assert_called_once_with(gate.id)
    query.message.edit_reply_markup.assert_called_once_with(reply_markup=None)


async def test_gate_stop_noop_if_no_pending_gate():
    g = _goal(GoalStatus.AWAITING_GATE)
    bot, _, executor = _make_bot(goal=g, gate=None)
    query = _make_query(f"goal_stuck:gate_stop:{g.id.hex}")
    await bot._handle_stuck_callback(query, query.data)
    executor.handle_gate_stopped.assert_not_called()
