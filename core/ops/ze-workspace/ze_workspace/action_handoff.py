from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from ze_logging import get_logger
from ze_memory.action_records.recorder import ActionRecorder
from ze_memory.action_records.store import ActionRecordStore
from ze_memory.action_records.types import ActionContext, ActionRecord

from ze_workspace.action_records import (
    _actor_for,
    _lifecycle_for,
    _provenance_for,
    _summary_for,
    workspace_idempotency_key,
)
from ze_workspace.store import WorkspaceStore
from ze_workspace.types import WorkspaceRun

log = get_logger(__name__)

_action_store: ActionRecordStore | None = None
_workspace_store: WorkspaceStore | None = None


def configure_action_ledger(
    *,
    action_record_store: ActionRecordStore | None,
    workspace_store: WorkspaceStore | None,
) -> None:
    global _action_store, _workspace_store
    _action_store = action_record_store
    _workspace_store = workspace_store


async def record_workspace_run(run: WorkspaceRun) -> ActionRecord | None:
    if _action_store is None or run.id is None:
        return None
    key = workspace_idempotency_key(run)
    if _workspace_store is not None:
        await _workspace_store.mark_ledger_handoff(run.id, key=key, pending=True)
    lifecycle, outcome, failure_code = _lifecycle_for(run)
    recorder = ActionRecorder(_action_store)
    occurred = run.ended_at or run.started_at or datetime.now(timezone.utc)
    try:
        record = await recorder.record_action(
            producer_kind="workspace",
            source_record_type="workspace_run",
            source_record_id=str(run.id),
            action_kind="run",
            lifecycle=lifecycle,
            outcome=outcome,
            actor=_actor_for(run),
            producer_plugin="ze-workspace",
            occurred_at=occurred,
            summary=_summary_for(run, lifecycle),
            context=ActionContext(
                message_id=run.message_id if isinstance(run.message_id, UUID) else None,
                workspace_run_id=run.id if isinstance(run.id, UUID) else None,
            ),
            failure_code=failure_code,
            provenance=_provenance_for(run),
            confidence_value=0.4 if run.status is None else 1.0,
        )
    except Exception as exc:
        log.warning(
            "action_record_delivery_failed",
            producer_plugin="ze-workspace",
            authoritative_domain="workspace.workspace_run",
            authoritative_record_id=str(run.id),
            idempotency_key=key,
            error=type(exc).__name__,
        )
        return None
    if _workspace_store is not None:
        await _workspace_store.mark_ledger_handoff(run.id, key=key, pending=False)
    log.info(
        "action_record_delivered",
        producer_plugin="ze-workspace",
        record_id=str(getattr(record, "id", record)),
        idempotency_key=key,
    )
    return record


async def retry_pending_workspace_action_records() -> int:
    if _action_store is None or _workspace_store is None:
        return 0
    pending = await _workspace_store.list_ledger_pending()
    delivered = 0
    for run in pending:
        if await record_workspace_run(run) is not None:
            delivered += 1
    return delivered
