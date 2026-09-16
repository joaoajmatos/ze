from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_memory.action_records.recorder import idempotency_key as make_idempotency_key
from ze_memory.action_records.types import (
    ActionContext,
    ActionLifecycle,
    ActionOutcome,
    ActionRecordDraft,
    AuthoritativeRef,
)
from ze_plugin.contribution import Contribution, SourceFunction, TargetFace

from ze_workspace.sanitize import redact
from ze_workspace.types import WorkspaceRun, WorkspaceRunOrigin, WorkspaceRunStatus

AUTHORITATIVE_DOMAIN = "workspace.runs"

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


def draft_from_workspace_run(run: WorkspaceRun) -> ActionRecordDraft:
    lifecycle, outcome, failure_code = _lifecycle_for(run)
    workspace_run_id = run.id if isinstance(run.id, UUID) else None
    message_id = run.message_id if isinstance(run.message_id, UUID) else None
    return ActionRecordDraft(
        idempotency_key=workspace_idempotency_key(run),
        action_type="workspace.run",
        actor=_actor_for(run),
        producer_plugin="ze-workspace",
        lifecycle=lifecycle,
        outcome=outcome,
        occurred_at=run.ended_at or run.started_at or datetime.now(timezone.utc),
        summary=_summary_for(run, lifecycle),
        authoritative_ref=AuthoritativeRef(
            domain=AUTHORITATIVE_DOMAIN,
            record_id=str(run.id),
        ),
        context=ActionContext(
            message_id=message_id,
            workspace_run_id=workspace_run_id,
        ),
        failure_code=failure_code,
    )


def contribution_from_workspace_run(run: WorkspaceRun) -> Contribution:
    return Contribution(
        claim_kind=ClaimKind.ACTION_RECORD,
        provenance=_provenance_for(run),
        confidence=Confidence(
            value=0.4 if run.status is None else 1.0,
            decay_profile=DecayProfile.TIME_LINEAR,
        ),
        target_face=TargetFace.WORLD,
        source_function=SourceFunction.ACTION,
        action_record=draft_from_workspace_run(run),
    )
