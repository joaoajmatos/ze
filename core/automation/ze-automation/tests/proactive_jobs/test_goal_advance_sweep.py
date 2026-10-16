"""goal_advance_sweep: cron and switch come from config; the sweep itself only advances active goals."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_automation.bootstrap import register_goal_advance_sweep


def _settings(proactive: dict | None = None):
    return SimpleNamespace(config={"proactive": proactive or {}})


def _stack(goals):
    return SimpleNamespace(
        goal_store=SimpleNamespace(list_for_advance=AsyncMock(return_value=goals)),
        goal_executor=SimpleNamespace(advance=AsyncMock()),
    )


def test_default_cron_is_every_fifteen_minutes():
    scheduler = MagicMock()
    register_goal_advance_sweep(scheduler, _settings(), _stack([]))
    kwargs = scheduler.add_cron_job.call_args.kwargs
    assert kwargs["cron"] == "*/15 * * * *"
    assert kwargs["job_id"] == "goal_advance_sweep"


def test_cron_is_configurable():
    scheduler = MagicMock()
    settings = _settings({"goal_advance_sweep": {"cron": "0 * * * *"}})
    register_goal_advance_sweep(scheduler, settings, _stack([]))
    assert scheduler.add_cron_job.call_args.kwargs["cron"] == "0 * * * *"


def test_can_be_switched_off():
    scheduler = MagicMock()
    settings = _settings({"goal_advance_sweep": {"enabled": False}})
    register_goal_advance_sweep(scheduler, settings, _stack([]))
    scheduler.add_cron_job.assert_not_called()


async def test_sweep_advances_each_active_goal_once():
    import asyncio

    goals = [SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())]
    stack = _stack(goals)
    scheduler = MagicMock()
    register_goal_advance_sweep(scheduler, _settings(), stack)

    await scheduler.add_cron_job.call_args.kwargs["fn"]()
    await asyncio.sleep(0)

    advanced = [c.args[0] for c in stack.goal_executor.advance.await_args_list]
    assert advanced == [g.id for g in goals]


async def test_sweep_with_no_active_goals_does_nothing():
    stack = _stack([])
    scheduler = MagicMock()
    register_goal_advance_sweep(scheduler, _settings(), stack)
    await scheduler.add_cron_job.call_args.kwargs["fn"]()
    stack.goal_executor.advance.assert_not_awaited()
