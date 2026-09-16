from __future__ import annotations

from ze_agents.errors import (
    ActionRecordIdempotencyConflictError,
    ActionRecordValidationError,
    ZeCoreError,
)


class ActionRecordError(ZeCoreError):
    """Base class for action-record ledger errors."""


class ActionRecordNotFoundError(ActionRecordError):
    """Cited retry_of, supersedes, or evidence ActionRecord does not exist."""


class UnsafeActionRecordSummaryError(ActionRecordValidationError):
    """Summary or failure_code contains forbidden sensitive content."""


class InvalidActionRecordStateError(ActionRecordValidationError):
    """Lifecycle/outcome combination is not a truthful observation."""


class ActionRecordConflictError(ActionRecordIdempotencyConflictError):
    """Idempotency key reused with a materially different observation."""
