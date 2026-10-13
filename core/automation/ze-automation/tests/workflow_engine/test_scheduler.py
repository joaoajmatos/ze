from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_automation.workflow.scheduler import WorkflowScheduler
from ze_automation.workflow.types import Workflow, WorkflowExecution


def _make_workflow(**overrides) -> Workflow:
    defaults = dict(
        id=uuid4(),
        name="Trump Health Developments",
        description="Monitor for breaking news",
        steps=[],
        schedule="0 9 * * *",
        enabled=True,
        last_run_at=None,
        next_run_at=None,
        created_at=None,
        updated_at=None,
    )
    defaults.update(overrides)
    return Workflow(**defaults)


def _make_store(execution: WorkflowExecution | None) -> MagicMock:
    store = MagicMock()
    store.get_execution = AsyncMock(return_value=execution)
    store.finish_execution = AsyncMock()
    store.update_run_timestamps = AsyncMock()
    store.recover_stale = AsyncMock(return_value=0)
    return store


async def test_step_failure_triggers_on_failure_without_raising():
    workflow = _make_workflow()
    execution_id = uuid4()
    failed_execution = WorkflowExecution(
        id=execution_id,
        workflow_id=workflow.id,
        status="failed",
        error="Step 3 (search for breaking news) failed: no results",
    )
    store = _make_store(failed_execution)
    on_failure = AsyncMock()

    async def executor(_wf, _exec_id):
        return None  # graph routed to workflow_failed and returned normally

    scheduler = WorkflowScheduler(
        workflow_store=store, executor=executor, on_failure=on_failure
    )

    await scheduler._run_execution(workflow, execution_id)

    on_failure.assert_called_once()
    called_workflow, called_exc = on_failure.call_args.args
    assert called_workflow is workflow
    assert "no results" in str(called_exc)
    store.update_run_timestamps.assert_not_called()


async def test_successful_execution_updates_run_timestamps_and_skips_on_failure():
    workflow = _make_workflow()
    execution_id = uuid4()
    completed_execution = WorkflowExecution(
        id=execution_id, workflow_id=workflow.id, status="completed"
    )
    store = _make_store(completed_execution)
    on_failure = AsyncMock()

    async def executor(_wf, _exec_id):
        return None

    scheduler = WorkflowScheduler(
        workflow_store=store, executor=executor, on_failure=on_failure
    )

    await scheduler._run_execution(workflow, execution_id)

    on_failure.assert_not_called()
    store.update_run_timestamps.assert_called_once()


async def test_raised_exception_still_triggers_on_failure():
    workflow = _make_workflow()
    execution_id = uuid4()
    store = _make_store(execution=None)
    on_failure = AsyncMock()

    async def executor(_wf, _exec_id):
        raise RuntimeError("boom")

    scheduler = WorkflowScheduler(
        workflow_store=store, executor=executor, on_failure=on_failure
    )

    await scheduler._run_execution(workflow, execution_id)

    on_failure.assert_called_once()
    store.finish_execution.assert_called_once_with(execution_id, "failed", error="boom")
    store.get_execution.assert_not_called()


def test_add_job_prevents_concurrent_overlapping_runs():
    workflow = _make_workflow()
    store = _make_store(execution=None)
    scheduler = WorkflowScheduler(workflow_store=store, executor=AsyncMock())

    scheduler._add_job(workflow)

    job = scheduler._scheduler.get_job(str(workflow.id))
    assert job.max_instances == 1
    assert job.coalesce is True


async def test_cancel_execution_marks_running_execution():
    workflow = _make_workflow()
    execution_id = uuid4()
    running = WorkflowExecution(
        id=execution_id,
        workflow_id=workflow.id,
        status="running",
    )
    store = _make_store(running)
    scheduler = WorkflowScheduler(workflow_store=store, executor=AsyncMock())
    scheduler._running_executions.add(execution_id)
    scheduler._cancellation.register(execution_id)

    status = await scheduler.cancel_execution(workflow.id, execution_id)

    assert status == "cancelled"
    assert scheduler.is_cancelled(execution_id)


async def test_cancel_execution_returns_not_running_for_finished():
    workflow = _make_workflow()
    execution_id = uuid4()
    completed = WorkflowExecution(
        id=execution_id,
        workflow_id=workflow.id,
        status="completed",
    )
    store = _make_store(completed)
    scheduler = WorkflowScheduler(workflow_store=store, executor=AsyncMock())

    status = await scheduler.cancel_execution(workflow.id, execution_id)

    assert status == "not_running"


async def test_start_recovers_stale_executions_before_scheduling():
    workflow = _make_workflow()
    store = _make_store(execution=None)
    store.list_enabled_scheduled = AsyncMock(return_value=[workflow])
    scheduler = WorkflowScheduler(
        workflow_store=store, executor=AsyncMock(), stale_timeout_minutes=45
    )

    await scheduler.start()

    store.recover_stale.assert_called_once_with(45)
    await scheduler.stop()


# ── catch-up (phase 177) ──────────────────────────────────────────────────────


def _catchup_scheduler(workflow, executions):
    from datetime import datetime, timedelta, timezone  # noqa: F401

    store = _make_store(None)
    store.list_enabled_scheduled = AsyncMock(return_value=[workflow])
    store.list_executions = AsyncMock(return_value=executions)
    scheduler = WorkflowScheduler(workflow_store=store, executor=AsyncMock())
    scheduler.trigger_now = AsyncMock()
    return scheduler, store


async def _start_and_stop(scheduler):
    await scheduler.start()
    await scheduler.stop()


async def test_missed_scheduled_workflow_triggers_once():
    from datetime import datetime, timedelta, timezone

    wf = _make_workflow(schedule="* * * * *")
    ex = WorkflowExecution(
        id=uuid4(),
        workflow_id=wf.id,
        status="completed",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=30),
    )
    scheduler, store = _catchup_scheduler(wf, [ex])
    await _start_and_stop(scheduler)
    scheduler.trigger_now.assert_awaited_once_with(wf.id)
    store.list_executions.assert_awaited_once_with(wf.id, limit=1)


async def test_workflow_without_executions_is_not_caught_up():
    wf = _make_workflow(schedule="* * * * *")
    scheduler, _ = _catchup_scheduler(wf, [])
    await _start_and_stop(scheduler)
    scheduler.trigger_now.assert_not_awaited()


async def test_workflow_not_missed_is_not_caught_up():
    from datetime import datetime, timezone

    wf = _make_workflow(schedule="0 9 * * *")
    ex = WorkflowExecution(
        id=uuid4(),
        workflow_id=wf.id,
        status="completed",
        started_at=datetime.now(timezone.utc),
    )
    scheduler, _ = _catchup_scheduler(wf, [ex])
    await _start_and_stop(scheduler)
    scheduler.trigger_now.assert_not_awaited()


async def test_jobs_have_no_misfire_limit():
    wf = _make_workflow()
    scheduler, _ = _catchup_scheduler(wf, [])
    scheduler._add_job(wf)
    assert scheduler._scheduler.get_job(str(wf.id)).misfire_grace_time is None
    scheduler.schedule_job(AsyncMock(), "0 8 * * *", "x")
    assert scheduler._scheduler.get_job("x").misfire_grace_time is None
