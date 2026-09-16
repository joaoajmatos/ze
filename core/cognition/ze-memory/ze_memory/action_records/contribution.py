from __future__ import annotations

from uuid import UUID

from ze_agents.claims import ClaimKind
from ze_agents.errors import ActionRecordValidationError
from ze_plugin.contribution import Contribution, SourceFunction, validate_and_submit

from ze_memory.action_records.errors import ActionRecordNotFoundError
from ze_memory.action_records.store import ActionRecordStore
from ze_memory.action_records.types import ActionRecord, validate_draft


async def submit_action_record(
    store: ActionRecordStore,
    contribution: Contribution,
) -> ActionRecord:
    """Validate Action doctrine, then append exactly once via the contribution seam."""
    if contribution.source_function is not SourceFunction.ACTION:
        raise ActionRecordValidationError(
            "ActionRecords must be submitted with source_function ACTION"
        )
    if contribution.claim_kind is not ClaimKind.ACTION_RECORD:
        raise ActionRecordValidationError(
            "ActionRecords must be submitted with claim_kind ACTION_RECORD"
        )
    if contribution.action_record is None:
        raise ActionRecordValidationError("missing action_record payload")
    contribution.action_record = validate_draft(contribution.action_record)
    draft = contribution.action_record

    if draft.retry_of is not None and await store.get(draft.retry_of) is None:
        raise ActionRecordNotFoundError(f"retry_of {draft.retry_of} does not exist")
    if draft.supersedes is not None and await store.get(draft.supersedes) is None:
        raise ActionRecordNotFoundError(f"supersedes {draft.supersedes} does not exist")
    for ref in draft.causal_refs:
        if ref.kind != "action_record":
            continue
        cited = ref.id if isinstance(ref.id, UUID) else UUID(str(ref.id))
        if await store.get(cited) is None:
            raise ActionRecordNotFoundError(
                f"causal action_record {cited} does not exist"
            )

    async def _write() -> ActionRecord:
        return await store.append(contribution)

    async def check_action_record_exists(record_id) -> bool:
        return await store.get(record_id) is not None

    return await validate_and_submit(
        contribution,
        _write,
        check_action_record_exists=check_action_record_exists,
    )
