from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_automation.bootstrap import make_workflow_failure_handler
from ze_automation.workflow.types import StepResult, WorkflowExecution, WorkflowStep


def _workflow():
    return SimpleNamespace(id=uuid4(), name="Weekly invoices")


def _failed_execution(workflow_id):
    return WorkflowExecution(
        id=uuid4(),
        workflow_id=workflow_id,
        status="failed",
        step_results=[
            StepResult(0, "Check the inbox", "", False, "TimeoutError: boom", 5)
        ],
        steps_snapshot=[WorkflowStep(task="Check the inbox")],
        error="TimeoutError: boom",
        created_at=datetime.now(timezone.utc),
    )


def _handler(executions, *, sent_recently=False):
    store = AsyncMock()
    store.list_executions = AsyncMock(return_value=executions)
    notifier = AsyncMock()
    push_log = AsyncMock()
    push_log.was_sent_within_hours = AsyncMock(return_value=sent_recently)
    settings = SimpleNamespace(proactive_config={})
    handler = make_workflow_failure_handler(
        settings=settings, workflow_store=store, notifier=notifier, push_log_store=push_log
    )
    return handler, notifier, push_log


async def test_push_points_at_the_execution_inside_its_workflow():
    workflow = _workflow()
    execution = _failed_execution(workflow.id)
    handler, notifier, push_log = _handler([execution])

    await handler(workflow, RuntimeError("TimeoutError: boom"))

    args = notifier.notify.await_args
    assert args.args[2] == (
        "Step 1 of 1, “Check the inbox”, failed: it ran out of time."
    )
    assert args.kwargs["target_type"] == "workflow_execution"
    assert args.kwargs["target_id"] == str(execution.id)
    assert args.kwargs["target_parent_id"] == str(workflow.id)
    push_log.log.assert_awaited_once()


async def test_a_newer_run_in_flight_does_not_hide_the_failed_one():
    workflow = _workflow()
    failed = _failed_execution(workflow.id)
    running = WorkflowExecution(
        id=uuid4(),
        workflow_id=workflow.id,
        status="running",
        step_results=[],
        steps_snapshot=[],
        created_at=datetime.now(timezone.utc),
    )
    handler, notifier, _ = _handler([running, failed])

    await handler(workflow, RuntimeError("boom"))

    assert notifier.notify.await_args.kwargs["target_id"] == str(failed.id)


async def test_without_an_execution_the_body_says_it_never_started_and_nothing_is_targeted():
    workflow = _workflow()
    handler, notifier, _ = _handler([])

    await handler(workflow, RuntimeError("scheduler blew up"))

    args = notifier.notify.await_args
    assert args.args[2] == "The run failed before it started."
    assert args.kwargs.get("target_type") is None
    assert args.kwargs.get("target_id") is None


async def test_cooldown_suppresses_the_push():
    workflow = _workflow()
    handler, notifier, _ = _handler([_failed_execution(workflow.id)], sent_recently=True)
    await handler(workflow, RuntimeError("x"))
    notifier.notify.assert_not_awaited()


async def test_disabled_alerts_send_nothing():
    workflow = _workflow()
    handler, notifier, _ = _handler([_failed_execution(workflow.id)])
    handler_disabled = make_workflow_failure_handler(
        settings=SimpleNamespace(
            proactive_config={"alerts": {"workflow_failure_enabled": False}}
        ),
        workflow_store=AsyncMock(),
        notifier=notifier,
        push_log_store=AsyncMock(),
    )
    await handler_disabled(workflow, RuntimeError("x"))
    notifier.notify.assert_not_awaited()
