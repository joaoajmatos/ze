from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from ze_agents.claims import Confidence, Provenance
from ze_plugin.contribution import EvidenceRef, TargetFace

from ze_memory.action_records.errors import InvalidActionRecordStateError
from ze_memory.action_records.sanitize import (
    assert_safe_text,
    sanitize_failure_code,
    sanitize_summary,
)

TERMINAL_LIFECYCLES = frozenset(
    {
        "succeeded",
        "failed",
        "cancelled",
        "partial",
        "timed_out",
        "unknown",
    }
)

NON_TERMINAL_LIFECYCLES = frozenset({"started", "in_progress"})


class ActionLifecycle(StrEnum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"
    TIMED_OUT = "timed_out"
    UNKNOWN = "unknown"


class ActionOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


_ALLOWED_OUTCOMES: dict[ActionLifecycle, ActionOutcome | None] = {
    ActionLifecycle.STARTED: None,
    ActionLifecycle.IN_PROGRESS: None,
    ActionLifecycle.SUCCEEDED: ActionOutcome.SUCCESS,
    ActionLifecycle.FAILED: ActionOutcome.FAILURE,
    ActionLifecycle.CANCELLED: ActionOutcome.CANCELLED,
    ActionLifecycle.PARTIAL: ActionOutcome.PARTIAL,
    ActionLifecycle.TIMED_OUT: ActionOutcome.TIMEOUT,
    ActionLifecycle.UNKNOWN: ActionOutcome.UNKNOWN,
}

CausalKind = Literal[
    "fact",
    "episode",
    "signal",
    "goal",
    "workflow",
    "open_loop",
    "approval",
    "action_record",
]


@dataclass(frozen=True)
class AuthoritativeRef:
    domain: str
    record_id: str


@dataclass(frozen=True)
class CausalRef:
    kind: CausalKind
    id: UUID | str


@dataclass(frozen=True)
class ActionContext:
    request_id: UUID | None = None
    session_id: UUID | None = None
    message_id: UUID | None = None
    thread_id: UUID | None = None
    goal_id: UUID | None = None
    milestone_id: UUID | None = None
    workflow_id: UUID | None = None
    workflow_run_id: UUID | None = None
    workspace_run_id: UUID | None = None
    channel_id: UUID | None = None
    outreach_id: UUID | None = None
    calendar_ref: str | None = None
    reminder_id: UUID | None = None


@dataclass(frozen=True)
class ActionRecordDraft:
    idempotency_key: str
    action_type: str
    actor: str
    producer_plugin: str
    lifecycle: ActionLifecycle
    outcome: ActionOutcome | None
    occurred_at: datetime
    summary: str
    authoritative_ref: AuthoritativeRef
    context: ActionContext = field(default_factory=ActionContext)
    causal_refs: list[CausalRef] = field(default_factory=list)
    retry_of: UUID | None = None
    supersedes: UUID | None = None
    failure_code: str | None = None


@dataclass(frozen=True)
class ActionRecord:
    id: UUID
    idempotency_key: str
    action_type: str
    actor: str
    producer_plugin: str
    lifecycle: ActionLifecycle
    outcome: ActionOutcome | None
    occurred_at: datetime
    provenance: Provenance
    confidence: Confidence
    target_face: TargetFace
    summary: str
    authoritative_ref: AuthoritativeRef
    context: ActionContext
    evidence: list[EvidenceRef]
    causal_refs: list[CausalRef]
    retry_of: UUID | None
    supersedes: UUID | None
    failure_code: str | None
    created_at: datetime | None = None


def validate_draft(draft: ActionRecordDraft) -> ActionRecordDraft:
    if not draft.idempotency_key.strip():
        raise InvalidActionRecordStateError("idempotency_key must be non-empty")
    if not draft.action_type.strip():
        raise InvalidActionRecordStateError("action_type must be non-empty")
    if not draft.actor.strip():
        raise InvalidActionRecordStateError("actor must be non-empty")
    if not draft.producer_plugin.strip():
        raise InvalidActionRecordStateError("producer_plugin must be non-empty")
    if not draft.authoritative_ref.domain.strip():
        raise InvalidActionRecordStateError(
            "authoritative_ref.domain must be non-empty"
        )
    if not str(draft.authoritative_ref.record_id).strip():
        raise InvalidActionRecordStateError(
            "authoritative_ref.record_id must be non-empty"
        )

    allowed = _ALLOWED_OUTCOMES[draft.lifecycle]
    if allowed is None:
        if draft.outcome is not None:
            raise InvalidActionRecordStateError(
                f"{draft.lifecycle.value} observations must not include an outcome"
            )
        if draft.failure_code is not None:
            raise InvalidActionRecordStateError(
                f"{draft.lifecycle.value} observations must not include a failure_code"
            )
    else:
        if draft.outcome is None:
            raise InvalidActionRecordStateError(
                f"{draft.lifecycle.value} observations require an outcome"
            )
        if draft.outcome is not allowed:
            raise InvalidActionRecordStateError(
                f"{draft.lifecycle.value} requires outcome {allowed.value}"
            )
        if (
            draft.lifecycle
            in {
                ActionLifecycle.FAILED,
                ActionLifecycle.TIMED_OUT,
                ActionLifecycle.UNKNOWN,
            }
            and not (draft.failure_code or "").strip()
        ):
            raise InvalidActionRecordStateError(
                f"{draft.lifecycle.value} observations require a failure_code"
            )

    summary = sanitize_summary(draft.summary)
    assert_safe_text(summary, field="summary")
    failure_code = sanitize_failure_code(draft.failure_code)
    if failure_code:
        assert_safe_text(failure_code, field="failure_code")

    return ActionRecordDraft(
        idempotency_key=draft.idempotency_key.strip(),
        action_type=draft.action_type.strip(),
        actor=draft.actor.strip(),
        producer_plugin=draft.producer_plugin.strip(),
        lifecycle=draft.lifecycle,
        outcome=draft.outcome,
        occurred_at=draft.occurred_at,
        summary=summary,
        authoritative_ref=AuthoritativeRef(
            domain=draft.authoritative_ref.domain.strip(),
            record_id=str(draft.authoritative_ref.record_id).strip(),
        ),
        context=draft.context,
        causal_refs=list(draft.causal_refs),
        retry_of=draft.retry_of,
        supersedes=draft.supersedes,
        failure_code=failure_code,
    )


def material_tuple(draft: ActionRecordDraft) -> tuple:
    ref = draft.authoritative_ref
    return (
        draft.action_type,
        draft.actor,
        draft.producer_plugin,
        draft.lifecycle.value,
        None if draft.outcome is None else draft.outcome.value,
        ref.domain,
        ref.record_id,
        draft.summary,
        draft.failure_code,
        None if draft.retry_of is None else str(draft.retry_of),
        None if draft.supersedes is None else str(draft.supersedes),
    )
