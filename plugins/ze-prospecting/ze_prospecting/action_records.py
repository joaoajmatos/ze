from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from ze_memory.action_records.recorder import ActionRecorder, safe_record_action
from ze_memory.action_records.store import ActionRecordStore
from ze_memory.action_records.types import ActionContext, ActionLifecycle, ActionOutcome

_recorder: ActionRecorder | None = None


def configure_action_recorder(store: ActionRecordStore | None) -> None:
    global _recorder
    _recorder = ActionRecorder(store) if store is not None else None


async def emit_outreach_event(outreach_id: UUID, event_type: str) -> None:
    if event_type in {"sent", "replied"}:
        lifecycle, outcome, failure_code = (
            ActionLifecycle.SUCCEEDED,
            ActionOutcome.SUCCESS,
            None,
        )
    elif event_type in {"failed", "bounced"}:
        lifecycle, outcome, failure_code = (
            ActionLifecycle.FAILED,
            ActionOutcome.FAILURE,
            event_type,
        )
    else:
        lifecycle, outcome, failure_code = (
            ActionLifecycle.IN_PROGRESS,
            None,
            None,
        )
    await safe_record_action(
        _recorder,
        producer_kind="prospecting",
        source_record_type="prospect_outreach",
        source_record_id=str(outreach_id),
        action_kind=event_type,
        lifecycle=lifecycle,
        outcome=outcome,
        actor="prospecting",
        producer_plugin="ze-prospecting",
        occurred_at=datetime.now(timezone.utc),
        summary=f"prospect outreach {event_type}",
        context=ActionContext(outreach_id=outreach_id),
        failure_code=failure_code,
        confidence_value=1.0 if outcome is not None else 0.4,
    )
