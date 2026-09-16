from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ze_memory.action_records.errors import (
    InvalidActionRecordStateError,
    UnsafeActionRecordSummaryError,
)
from ze_memory.action_records.types import (
    ActionLifecycle,
    ActionOutcome,
    ActionRecordDraft,
    AuthoritativeRef,
    validate_draft,
)


def _draft(**overrides) -> ActionRecordDraft:
    base = dict(
        idempotency_key="ws:run:1:terminal",
        action_type="workspace.run",
        actor="workspace",
        producer_plugin="ze-workspace",
        lifecycle=ActionLifecycle.SUCCEEDED,
        outcome=ActionOutcome.SUCCESS,
        occurred_at=datetime.now(timezone.utc),
        summary="workspace run succeeded",
        authoritative_ref=AuthoritativeRef(domain="workspace.runs", record_id="abc"),
        failure_code=None,
    )
    base.update(overrides)
    return ActionRecordDraft(**base)


def test_opaque_record_id_need_not_be_uuid() -> None:
    draft = validate_draft(
        _draft(
            authoritative_ref=AuthoritativeRef(
                domain="messenger.outbound", record_id="gmail-msg-not-a-uuid"
            )
        )
    )
    assert draft.authoritative_ref.record_id == "gmail-msg-not-a-uuid"


def test_started_forbids_outcome() -> None:
    with pytest.raises(InvalidActionRecordStateError):
        validate_draft(
            _draft(lifecycle=ActionLifecycle.STARTED, outcome=ActionOutcome.SUCCESS)
        )


def test_succeeded_requires_success_outcome() -> None:
    with pytest.raises(InvalidActionRecordStateError):
        validate_draft(
            _draft(lifecycle=ActionLifecycle.SUCCEEDED, outcome=ActionOutcome.FAILURE)
        )


def test_failed_requires_failure_code() -> None:
    with pytest.raises(InvalidActionRecordStateError):
        validate_draft(
            _draft(
                lifecycle=ActionLifecycle.FAILED,
                outcome=ActionOutcome.FAILURE,
                failure_code=None,
            )
        )


def test_unknown_is_not_success() -> None:
    draft = validate_draft(
        _draft(
            lifecycle=ActionLifecycle.UNKNOWN,
            outcome=ActionOutcome.UNKNOWN,
            failure_code="outcome_unobserved",
            summary="workspace run outcome unknown",
        )
    )
    assert draft.outcome is ActionOutcome.UNKNOWN
    assert draft.lifecycle is ActionLifecycle.UNKNOWN


@pytest.mark.parametrize(
    "summary",
    [
        'Traceback (most recent call last):\nFile "x.py", line 1',
        "password=hunter2",
        "Authorization: Bearer abcdef",
        "-----BEGIN RSA PRIVATE KEY-----",
    ],
)
def test_unsafe_summary_is_rejected(summary: str) -> None:
    with pytest.raises(UnsafeActionRecordSummaryError):
        validate_draft(_draft(summary=summary))


def test_summary_is_bounded() -> None:
    draft = validate_draft(_draft(summary="ok " * 400))
    assert len(draft.summary) <= 500
