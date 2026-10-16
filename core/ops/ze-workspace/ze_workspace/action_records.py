from __future__ import annotations


from ze_agents.claims import Provenance
from ze_memory.action_records.recorder import idempotency_key as make_idempotency_key
from ze_memory.action_records.types import (
    ActionLifecycle,
    ActionOutcome,
)

from ze_workspace.sanitize import redact
from ze_workspace.types import WorkspaceRun, WorkspaceRunOrigin, WorkspaceRunStatus


_LOST_SUMMARIES = {
    "the computer restarted and lost this run — no fabricated result",
    "ze-api restarted before this run reached the workspace computer",
}

_TERMINAL_MAP: dict[WorkspaceRunStatus, tuple[ActionLifecycle, ActionOutcome]] = {
    WorkspaceRunStatus.SUCCEEDED: (ActionLifecycle.SUCCEEDED, ActionOutcome.SUCCESS),
    WorkspaceRunStatus.FAILED: (ActionLifecycle.FAILED, ActionOutcome.FAILURE),
    WorkspaceRunStatus.TIMED_OUT: (ActionLifecycle.TIMED_OUT, ActionOutcome.TIMEOUT),
    WorkspaceRunStatus.CANCELLED: (ActionLifecycle.CANCELLED, ActionOutcome.CANCELLED),
    WorkspaceRunStatus.REFUSED: (ActionLifecycle.CANCELLED, ActionOutcome.CANCELLED),
}


def workspace_idempotency_key(run: WorkspaceRun) -> str:
    lifecycle, _, _ = _lifecycle_for(run)
    return make_idempotency_key(
        producer_kind="workspace",
        source_record_type="workspace_run",
        source_record_id=str(run.id),
        action_kind="run",
        lifecycle=lifecycle,
    )


def _lifecycle_for(
    run: WorkspaceRun,
) -> tuple[ActionLifecycle, ActionOutcome | None, str | None]:
    if run.status is None:
        return ActionLifecycle.STARTED, None, None
    if (
        run.status is WorkspaceRunStatus.FAILED
        and (run.error_summary or "") in _LOST_SUMMARIES
    ):
        return ActionLifecycle.UNKNOWN, ActionOutcome.UNKNOWN, "outcome_unobserved"
    lifecycle, outcome = _TERMINAL_MAP[run.status]
    failure_code = None
    if lifecycle is ActionLifecycle.FAILED:
        failure_code = "nonzero_exit" if run.exit_code else "workspace_failed"
    elif lifecycle is ActionLifecycle.TIMED_OUT:
        failure_code = "timed_out"
    elif lifecycle is ActionLifecycle.CANCELLED:
        failure_code = (
            "cancelled" if run.status is not WorkspaceRunStatus.REFUSED else "refused"
        )
    return lifecycle, outcome, failure_code


def _summary_for(run: WorkspaceRun, lifecycle: ActionLifecycle) -> str:
    exit_part = f" exit {run.exit_code}" if run.exit_code is not None else ""
    text = f"workspace run {lifecycle.value}{exit_part}"
    return redact(text)


def _actor_for(run: WorkspaceRun) -> str:
    if run.origin is WorkspaceRunOrigin.UNATTENDED:
        return "workspace.unattended"
    if run.origin is WorkspaceRunOrigin.USER:
        return "workspace.user"
    return "workspace.conversation"


def _provenance_for(run: WorkspaceRun) -> Provenance:
    if run.origin is WorkspaceRunOrigin.UNATTENDED:
        return Provenance.SYNTHESIZED
    return Provenance.PROMPT_SUPPLIED
