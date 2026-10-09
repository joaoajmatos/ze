from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ze_agents.claims import Confidence, Provenance
from ze_agents.errors import FeedbackRecordValidationError
from ze_plugin.contribution import TargetFace


class FeedbackKind(StrEnum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    CLEARED = "cleared"
    RETRY_REQUESTED = "retry_requested"


RATING_KINDS = frozenset(
    {FeedbackKind.THUMBS_UP, FeedbackKind.THUMBS_DOWN, FeedbackKind.CLEARED}
)


@dataclass(frozen=True)
class FeedbackRecordDraft:
    """One user reaction to one assistant message. Enumerated kind only, no free text."""

    idempotency_key: str
    message_id: UUID
    thread_id: str
    kind: FeedbackKind
    occurred_at: datetime
    trace_present: bool


@dataclass(frozen=True)
class FeedbackRecord:
    id: UUID
    idempotency_key: str
    message_id: UUID
    thread_id: str
    kind: FeedbackKind
    occurred_at: datetime
    provenance: Provenance
    confidence: Confidence
    target_face: TargetFace
    trace_present: bool
    created_at: datetime | None = None


def validate_draft(draft: FeedbackRecordDraft) -> FeedbackRecordDraft:
    if not draft.idempotency_key.strip():
        raise FeedbackRecordValidationError("idempotency_key must be non-empty")
    if not draft.thread_id.strip():
        raise FeedbackRecordValidationError("thread_id must be non-empty")
    if not isinstance(draft.kind, FeedbackKind):
        raise FeedbackRecordValidationError(f"unknown feedback kind: {draft.kind!r}")
    if draft.occurred_at.tzinfo is None:
        raise FeedbackRecordValidationError("occurred_at must be timezone-aware")
    return draft


def material_tuple(draft: FeedbackRecordDraft) -> tuple:
    return (draft.message_id, draft.thread_id, draft.kind)
