from __future__ import annotations

from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_agents.errors import FeedbackRecordValidationError
from ze_plugin.contribution import (
    Contribution,
    SourceFunction,
    TargetFace,
    validate_and_submit,
)

from ze_memory.feedback_records.store import FeedbackStore
from ze_memory.feedback_records.types import (
    FeedbackRecord,
    FeedbackRecordDraft,
    validate_draft,
)


def feedback_contribution(draft: FeedbackRecordDraft) -> Contribution:
    """A thumb is the user's own reaction (full confidence) about Ze's output, so the
    target face is WORLD, not USER: it must never invite user-profile consumers."""
    return Contribution(
        claim_kind=ClaimKind.FEEDBACK_RECORD,
        provenance=Provenance.PROMPT_SUPPLIED,
        confidence=Confidence(value=1.0, decay_profile=DecayProfile.TIME_LINEAR),
        target_face=TargetFace.WORLD,
        source_function=SourceFunction.PERCEPTION,
        feedback_record=draft,
    )


async def submit_feedback_record(
    store: FeedbackStore,
    contribution: Contribution,
) -> FeedbackRecord:
    """Validate Perception doctrine, then append exactly once via the contribution seam."""
    if contribution.source_function is not SourceFunction.PERCEPTION:
        raise FeedbackRecordValidationError(
            "FeedbackRecords must be submitted with source_function PERCEPTION"
        )
    if contribution.claim_kind is not ClaimKind.FEEDBACK_RECORD:
        raise FeedbackRecordValidationError(
            "FeedbackRecords must be submitted with claim_kind FEEDBACK_RECORD"
        )
    if contribution.feedback_record is None:
        raise FeedbackRecordValidationError("missing feedback_record payload")
    contribution.feedback_record = validate_draft(contribution.feedback_record)

    async def _write() -> FeedbackRecord:
        return await store.append(contribution)

    return await validate_and_submit(contribution, _write)
