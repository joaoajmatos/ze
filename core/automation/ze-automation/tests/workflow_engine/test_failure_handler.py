from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

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


class _PushLog:
    def __init__(self, *, seeded=()):
        self.keys = list(seeded)
        self.log = AsyncMock(side_effect=self._log)
        self.was_sent_within_hours = AsyncMock(side_effect=self._was_sent)

    async def _log(self, event_type, detail=None):
        self.keys.append(event_type)

    async def _was_sent(self, event_type, hours):
        return event_type in self.keys


def _handler(executions, *, sent_recently=None, outcome="delivered"):
    store = AsyncMock()
    store.list_executions = AsyncMock(return_value=executions)
    notifier = AsyncMock()
    notifier.notify = AsyncMock(return_value=outcome)
    push_log = _PushLog(seeded=[sent_recently] if sent_recently else [])
    settings = SimpleNamespace(proactive_config={})
    handler = make_workflow_failure_handler(
        settings=settings,
        workflow_store=store,
        notifier=notifier,
        push_log_store=push_log,
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
    assert push_log.keys == [
        f"workflow_failure:{workflow.id}",
        f"workflow_failure_alert:{workflow.id}",
    ]


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
    handler, notifier, _ = _handler(
        [_failed_execution(workflow.id)],
        sent_recently=f"workflow_failure_alert:{workflow.id}",
    )
    await handler(workflow, RuntimeError("x"))
    notifier.notify.assert_not_awaited()


@pytest.mark.parametrize("outcome", ["failed", "delivered", "held"])
async def test_every_failure_is_recorded_whatever_the_outcome(outcome):
    workflow = _workflow()
    handler, _, push_log = _handler([_failed_execution(workflow.id)], outcome=outcome)

    await handler(workflow, RuntimeError("x"))

    assert f"workflow_failure:{workflow.id}" in push_log.keys


async def test_a_failure_inside_the_cooldown_is_still_recorded():
    workflow = _workflow()
    handler, notifier, push_log = _handler(
        [_failed_execution(workflow.id)],
        sent_recently=f"workflow_failure_alert:{workflow.id}",
    )

    await handler(workflow, RuntimeError("x"))

    notifier.notify.assert_not_awaited()
    assert push_log.keys.count(f"workflow_failure:{workflow.id}") == 1


@pytest.mark.parametrize(
    ("outcome", "starts_cooldown"),
    [("failed", False), ("delivered", True), ("held", True)],
)
async def test_the_alert_cooldown_starts_only_when_delivered_or_held(
    outcome, starts_cooldown
):
    workflow = _workflow()
    handler, _, push_log = _handler([_failed_execution(workflow.id)], outcome=outcome)

    await handler(workflow, RuntimeError("x"))

    assert (f"workflow_failure_alert:{workflow.id}" in push_log.keys) is starts_cooldown


async def test_an_alert_that_failed_is_sent_again_on_the_next_failure():
    workflow = _workflow()
    handler, notifier, push_log = _handler(
        [_failed_execution(workflow.id)], outcome="failed"
    )

    await handler(workflow, RuntimeError("x"))
    await handler(workflow, RuntimeError("x"))

    assert notifier.notify.await_count == 2
    assert push_log.keys.count(f"workflow_failure:{workflow.id}") == 2


async def test_a_delivered_alert_suppresses_the_next_one_inside_the_cooldown():
    workflow = _workflow()
    handler, notifier, _ = _handler([_failed_execution(workflow.id)])

    await handler(workflow, RuntimeError("x"))
    await handler(workflow, RuntimeError("x"))

    assert notifier.notify.await_count == 1


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
