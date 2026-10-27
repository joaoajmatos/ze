from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4


from ze_automation.bootstrap import make_workflow_failure_handler
from ze_proactive.notifier import ProactiveNotifier
from ze_proactive.testing import InMemoryPushLog
from ze_proactive.types import NotificationRow, OncePer
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


def _handler(executions, *, outcome="delivered", settings=None):
    store = AsyncMock()
    store.list_executions = AsyncMock(return_value=executions)
    notifier = AsyncMock()
    notifier.notify = AsyncMock(return_value=outcome)
    handler = make_workflow_failure_handler(
        settings=settings or SimpleNamespace(proactive_config={}),
        workflow_store=store,
        notifier=notifier,
    )
    return handler, notifier


async def test_push_points_at_the_execution_inside_its_workflow():
    workflow = _workflow()
    execution = _failed_execution(workflow.id)
    handler, notifier = _handler([execution])

    await handler(workflow, RuntimeError("TimeoutError: boom"))

    args = notifier.notify.await_args
    assert args.args[2] == (
        "Step 1 of 1, “Check the inbox”, failed: it ran out of time."
    )
    assert args.kwargs["target_type"] == "workflow_execution"
    assert args.kwargs["target_id"] == str(execution.id)
    assert args.kwargs["target_parent_id"] == str(workflow.id)
    assert args.kwargs["once_per"] == OncePer(
        f"workflow_failure_alert:{workflow.id}", within=timedelta(hours=1)
    )


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
    handler, notifier = _handler([running, failed])

    await handler(workflow, RuntimeError("boom"))

    assert notifier.notify.await_args.kwargs["target_id"] == str(failed.id)


async def test_without_an_execution_the_body_says_it_never_started_and_nothing_is_targeted():
    workflow = _workflow()
    handler, notifier = _handler([])

    await handler(workflow, RuntimeError("scheduler blew up"))

    args = notifier.notify.await_args
    assert args.args[2] == "The run failed before it started."
    assert args.kwargs.get("target_type") is None
    assert args.kwargs.get("target_id") is None


async def test_the_cooldown_window_follows_the_configured_hours():
    workflow = _workflow()
    handler, notifier = _handler(
        [_failed_execution(workflow.id)],
        settings=SimpleNamespace(
            proactive_config={"alerts": {"workflow_failure_cooldown_hours": 6}}
        ),
    )

    await handler(workflow, RuntimeError("x"))

    assert notifier.notify.await_args.kwargs["once_per"].within == timedelta(hours=6)


async def _real_handler(workflow, *, interface, clock):
    store = AsyncMock()
    store.list_executions = AsyncMock(return_value=[_failed_execution(workflow.id)])
    notifier = ProactiveNotifier(
        interface,
        _notification_store(),
        push_log=InMemoryPushLog(clock=clock),
        clock=clock,
    )
    handler = make_workflow_failure_handler(
        settings=SimpleNamespace(proactive_config={}),
        workflow_store=store,
        notifier=notifier,
    )
    return handler


def _notification_store():
    store = AsyncMock()

    async def _create(**kw):
        return NotificationRow(
            id=str(uuid4()),
            event_type=kw["event_type"],
            source=kw["source"],
            title=kw["title"],
            body=kw["body"],
            target_type=kw.get("target_type"),
            target_id=kw.get("target_id"),
            target_parent_id=kw.get("target_parent_id"),
            push_class=kw["push_class"],
            urgency=kw["urgency"],
            format=kw["format"],
            actions=kw["actions"],
            delivery=kw["delivery"],
            created_at=datetime.now(timezone.utc),
            read_at=None,
        )

    store.create = AsyncMock(side_effect=_create)
    return store


async def test_a_failed_alert_is_sent_again_and_a_delivered_one_cools():
    workflow = _workflow()
    now = [datetime(2026, 10, 26, 9, tzinfo=timezone.utc)]
    interface = AsyncMock()
    interface.push = AsyncMock(side_effect=[RuntimeError("down"), None, None])
    handler = await _real_handler(workflow, interface=interface, clock=lambda: now[0])

    await handler(workflow, RuntimeError("x"))  # push raises -> failed, no claim
    await handler(workflow, RuntimeError("x"))  # delivered
    await handler(workflow, RuntimeError("x"))  # inside the window -> deduped

    assert interface.push.await_count == 2


async def test_disabled_alerts_send_nothing():
    workflow = _workflow()
    handler, notifier = _handler([_failed_execution(workflow.id)])
    handler_disabled = make_workflow_failure_handler(
        settings=SimpleNamespace(
            proactive_config={"alerts": {"workflow_failure_enabled": False}}
        ),
        workflow_store=AsyncMock(),
        notifier=notifier,
    )
    await handler_disabled(workflow, RuntimeError("x"))
    notifier.notify.assert_not_awaited()
