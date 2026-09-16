from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from ze_logging import get_logger
from ze_memory.action_records.recorder import ActionRecorder, safe_record_action
from ze_memory.action_records.store import ActionRecordStore
from ze_memory.action_records.types import ActionContext, ActionLifecycle, ActionOutcome

log = get_logger(__name__)

_recorder: ActionRecorder | None = None


def configure_action_recorder(store: ActionRecordStore | None) -> None:
    global _recorder
    _recorder = ActionRecorder(store) if store is not None else None


async def emit_calendar_mutation(
    *,
    action_kind: str,
    event_id: str,
    lifecycle: ActionLifecycle,
    outcome: ActionOutcome | None,
    failure_code: str | None = None,
) -> None:
    if not event_id:
        log.warning("action_record_skipped_missing_source", producer_plugin="ze-calendar")
        return
    await safe_record_action(
        _recorder,
        producer_kind="calendar",
        source_record_type="event",
        source_record_id=event_id,
        action_kind=action_kind,
        lifecycle=lifecycle,
        outcome=outcome,
        actor="calendar",
        producer_plugin="ze-calendar",
        occurred_at=datetime.now(timezone.utc),
        summary=f"calendar {action_kind} {lifecycle.value}",
        context=ActionContext(calendar_ref=event_id),
        failure_code=failure_code,
    )


async def emit_reminder_mutation(
    *,
    action_kind: str,
    reminder_id: str,
    lifecycle: ActionLifecycle,
    outcome: ActionOutcome | None,
    failure_code: str | None = None,
) -> None:
    if not reminder_id:
        log.warning("action_record_skipped_missing_source", producer_plugin="ze-calendar")
        return
    parsed: UUID | None
    try:
        parsed = UUID(reminder_id)
    except ValueError:
        parsed = None
    await safe_record_action(
        _recorder,
        producer_kind="reminder",
        source_record_type="reminder",
        source_record_id=reminder_id,
        action_kind=action_kind,
        lifecycle=lifecycle,
        outcome=outcome,
        actor="reminders",
        producer_plugin="ze-calendar",
        occurred_at=datetime.now(timezone.utc),
        summary=f"reminder {action_kind} {lifecycle.value}",
        context=ActionContext(reminder_id=parsed),
        failure_code=failure_code,
    )
