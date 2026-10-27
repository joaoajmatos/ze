"""Catch-up behaviour of ``WorkflowScheduler.start`` (phase 177, T037).

Mirrors ``contracts/catch-up.md`` → "``WorkflowScheduler.start()``":

After ``recover_stale``, for each enabled scheduled workflow with at least one
execution, compute ``missed_fire_time(schedule, latest.started_at, now, tz)``;
when it is not ``None``, ``await self.trigger_now(workflow.id)`` and log
``workflow_catch_up``. ``schedule_job``, ``schedule_at`` and ``_add_job`` all
set ``misfire_grace_time=None``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from ze_automation.workflow import scheduler as scheduler_module
from ze_automation.workflow.scheduler import WorkflowScheduler
from ze_automation.workflow.types import Workflow, WorkflowExecution


def _workflow(**overrides) -> Workflow:
    defaults = dict(
        id=uuid4(),
        name="Morning digest",
        description="",
        steps=[],
        schedule="0 8 * * *",
        enabled=True,
        last_run_at=None,
        next_run_at=None,
        created_at=None,
        updated_at=None,
    )
    defaults.update(overrides)
    return Workflow(**defaults)


def _execution(workflow: Workflow, started_at: datetime | None) -> WorkflowExecution:
    return WorkflowExecution(
        id=uuid4(),
        workflow_id=workflow.id,
        status="completed",
        started_at=started_at,
    )


def _store(
    workflows: list[Workflow],
    executions: dict[UUID, list[WorkflowExecution]] | None = None,
    side_effect=None,
) -> MagicMock:
    store = MagicMock()
    store.recover_stale = AsyncMock(return_value=0)
    store.list_enabled_scheduled = AsyncMock(return_value=workflows)
    if side_effect is not None:
        store.list_executions = AsyncMock(side_effect=side_effect)
    else:
        lookup = executions or {}
        store.list_executions = AsyncMock(
            side_effect=lambda workflow_id, limit=20: lookup.get(workflow_id, [])
        )
    return store


def _scheduler(store: MagicMock, *, enabled: bool = True) -> WorkflowScheduler:
    scheduler = WorkflowScheduler(
        workflow_store=store, executor=AsyncMock(), enabled=enabled
    )
    scheduler.trigger_now = AsyncMock()
    return scheduler


async def test_catch_up_passes_schedule_last_start_and_scheduler_tz(monkeypatch):
    workflow = _workflow(schedule="0 8 * * *")
    last_started = datetime.now(timezone.utc) - timedelta(days=1)
    store = _store([workflow], {workflow.id: [_execution(workflow, last_started)]})
    missed = MagicMock(return_value=None)
    monkeypatch.setattr(scheduler_module, "missed_fire_time", missed)

    scheduler = _scheduler(store)
    try:
        await scheduler.start()

        missed.assert_called_once()
        cron, last_run_at, now, tz = missed.call_args.args
        assert cron == "0 8 * * *"
        assert last_run_at == last_started
        assert now.tzinfo is not None
        assert tz == scheduler._scheduler.timezone
    finally:
        await scheduler.stop()


async def test_catch_up_awaits_trigger_now_when_a_fire_time_was_missed(monkeypatch):
    workflow = _workflow()
    last_started = datetime.now(timezone.utc) - timedelta(hours=2)
    store = _store([workflow], {workflow.id: [_execution(workflow, last_started)]})
    monkeypatch.setattr(
        scheduler_module,
        "missed_fire_time",
        MagicMock(return_value=datetime.now(timezone.utc) - timedelta(hours=1)),
    )

    scheduler = _scheduler(store)
    try:
        await scheduler.start()
        scheduler.trigger_now.assert_awaited_once_with(workflow.id)
        store.list_executions.assert_awaited_once_with(workflow.id, limit=1)
    finally:
        await scheduler.stop()


async def test_every_missed_workflow_is_caught_up():
    first = _workflow(name="First", schedule="* * * * *")
    second = _workflow(name="Second", schedule="* * * * *")
    last_started = datetime.now(timezone.utc) - timedelta(minutes=30)
    store = _store(
        [first, second],
        {
            first.id: [_execution(first, last_started)],
            second.id: [_execution(second, last_started)],
        },
    )

    scheduler = _scheduler(store)
    try:
        await scheduler.start()
        assert scheduler.trigger_now.await_count == 2
        triggered = [call.args[0] for call in scheduler.trigger_now.await_args_list]
        assert triggered == [first.id, second.id]
    finally:
        await scheduler.stop()


async def test_naive_last_start_is_treated_as_utc():
    workflow = _workflow(schedule="* * * * *")
    naive_started = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        minutes=30
    )
    assert naive_started.tzinfo is None
    store = _store([workflow], {workflow.id: [_execution(workflow, naive_started)]})

    scheduler = _scheduler(store)
    try:
        await scheduler.start()
        scheduler.trigger_now.assert_awaited_once_with(workflow.id)
    finally:
        await scheduler.stop()


async def test_workflow_with_null_last_start_is_not_caught_up():
    workflow = _workflow(schedule="* * * * *")
    store = _store([workflow], {workflow.id: [_execution(workflow, None)]})

    scheduler = _scheduler(store)
    try:
        await scheduler.start()
        scheduler.trigger_now.assert_not_awaited()
    finally:
        await scheduler.stop()


async def test_a_failed_lookup_does_not_block_later_workflows():
    broken = _workflow(name="Broken", schedule="* * * * *")
    healthy = _workflow(name="Healthy", schedule="* * * * *")
    last_started = datetime.now(timezone.utc) - timedelta(minutes=30)

    def lookup(workflow_id, limit=20):
        if workflow_id == broken.id:
            raise RuntimeError("execution lookup unavailable")
        return [_execution(healthy, last_started)]

    store = _store([broken, healthy], side_effect=lookup)

    scheduler = _scheduler(store)
    try:
        await scheduler.start()
        scheduler.trigger_now.assert_awaited_once_with(healthy.id)
    finally:
        await scheduler.stop()


async def test_catch_up_logs_workflow_catch_up(monkeypatch):
    workflow = _workflow(schedule="* * * * *")
    last_started = datetime.now(timezone.utc) - timedelta(minutes=30)
    store = _store([workflow], {workflow.id: [_execution(workflow, last_started)]})
    fake_log = MagicMock()
    monkeypatch.setattr(scheduler_module, "log", fake_log)

    scheduler = _scheduler(store)
    try:
        await scheduler.start()
        events = [call.args[0] for call in fake_log.info.call_args_list if call.args]
        assert "workflow_catch_up" in events
    finally:
        await scheduler.stop()


async def test_disabled_scheduler_does_not_catch_up():
    workflow = _workflow(schedule="* * * * *")
    last_started = datetime.now(timezone.utc) - timedelta(minutes=30)
    store = _store([workflow], {workflow.id: [_execution(workflow, last_started)]})

    scheduler = _scheduler(store, enabled=False)
    await scheduler.start()

    store.recover_stale.assert_not_awaited()
    store.list_enabled_scheduled.assert_not_awaited()
    scheduler.trigger_now.assert_not_awaited()


def test_schedule_at_has_no_misfire_limit():
    store = _store([])
    scheduler = _scheduler(store)
    scheduler.schedule_at(AsyncMock(), datetime.now(timezone.utc), "once")

    assert scheduler._scheduler.get_job("once").misfire_grace_time is None
