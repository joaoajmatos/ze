from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from ze_memory.action_records.recorder import ActionRecorder, safe_record_action
from ze_memory.action_records.store import ActionRecordStore
from ze_memory.action_records.types import ActionContext, ActionLifecycle, ActionOutcome
from ze_automation.goals.types import ExecutionTrace

_recorder: ActionRecorder | None = None


def configure_action_recorder(store: ActionRecordStore | None) -> None:
    global _recorder
    _recorder = ActionRecorder(store) if store is not None else None


def _lifecycle_from_success(success: bool) -> tuple[ActionLifecycle, ActionOutcome, str | None]:
    if success:
        return ActionLifecycle.SUCCEEDED, ActionOutcome.SUCCESS, None
    return ActionLifecycle.FAILED, ActionOutcome.FAILURE, "trace_failed"


async def emit_goal_traces(traces: list[ExecutionTrace]) -> None:
    for trace in traces:
        source_id = str(getattr(trace, "id", None) or f"{trace.goal_id}:{trace.milestone_id}:{trace.seq}")
        lifecycle, outcome, failure_code = _lifecycle_from_success(bool(trace.success))
        await safe_record_action(
            _recorder,
            producer_kind="goal",
            source_record_type="goal_execution_trace",
            source_record_id=source_id,
            action_kind=trace.tool_name or "trace",
            lifecycle=lifecycle,
            outcome=outcome,
            actor="goal_executor",
            producer_plugin="ze-automation",
            occurred_at=datetime.now(timezone.utc),
            summary=f"goal trace {lifecycle.value}",
            context=ActionContext(
                goal_id=trace.goal_id,
                milestone_id=trace.milestone_id,
            ),
            failure_code=failure_code,
        )


async def emit_workflow_started(execution_id: UUID, workflow_id: UUID | None) -> None:
    await safe_record_action(
        _recorder,
        producer_kind="workflow",
        source_record_type="workflow_execution",
        source_record_id=str(execution_id),
        action_kind="execute",
        lifecycle=ActionLifecycle.STARTED,
        outcome=None,
        actor="workflow_scheduler",
        producer_plugin="ze-automation",
        occurred_at=datetime.now(timezone.utc),
        summary="workflow execution started",
        context=ActionContext(
            workflow_id=workflow_id,
            workflow_run_id=execution_id,
        ),
        confidence_value=0.4,
    )


async def emit_workflow_finished(execution_id: UUID, status: str) -> None:
    mapping = {
        "completed": (ActionLifecycle.SUCCEEDED, ActionOutcome.SUCCESS, None),
        "success": (ActionLifecycle.SUCCEEDED, ActionOutcome.SUCCESS, None),
        "cancelled": (ActionLifecycle.CANCELLED, ActionOutcome.CANCELLED, "cancelled"),
        "failed": (ActionLifecycle.FAILED, ActionOutcome.FAILURE, "workflow_failed"),
    }
    lifecycle, outcome, failure_code = mapping.get(
        status, (ActionLifecycle.UNKNOWN, ActionOutcome.UNKNOWN, "outcome_unobserved")
    )
    await safe_record_action(
        _recorder,
        producer_kind="workflow",
        source_record_type="workflow_execution",
        source_record_id=str(execution_id),
        action_kind="execute",
        lifecycle=lifecycle,
        outcome=outcome,
        actor="workflow_scheduler",
        producer_plugin="ze-automation",
        occurred_at=datetime.now(timezone.utc),
        summary=f"workflow execution {lifecycle.value}",
        context=ActionContext(workflow_run_id=execution_id),
        failure_code=failure_code,
    )
