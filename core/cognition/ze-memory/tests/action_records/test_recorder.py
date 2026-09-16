from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

from ze_plugin.contribution import Contribution
from ze_memory.action_records.recorder import ActionRecorder, idempotency_key
from ze_memory.action_records.types import (
    ActionContext,
    ActionLifecycle,
    ActionOutcome,
    ActionRecord,
    ActionRecordDraft,
)


class InMemoryActionRecordStore:
    def __init__(self) -> None:
        self.by_id: dict[UUID, ActionRecord] = {}
        self.by_key: dict[str, ActionRecord] = {}
        self.lock = asyncio.Lock()
        self.append_calls = 0

    async def append(self, contribution: Contribution) -> ActionRecord:
        self.append_calls += 1
        draft: ActionRecordDraft = contribution.action_record
        async with self.lock:
            existing = self.by_key.get(draft.idempotency_key)
            if existing is not None:
                return existing
            record = ActionRecord(
                id=uuid4(),
                idempotency_key=draft.idempotency_key,
                action_type=draft.action_type,
                actor=draft.actor,
                producer_plugin=draft.producer_plugin,
                lifecycle=draft.lifecycle,
                outcome=draft.outcome,
                occurred_at=draft.occurred_at,
                provenance=contribution.provenance,
                confidence=contribution.confidence,
                target_face=contribution.target_face,
                summary=draft.summary,
                authoritative_ref=draft.authoritative_ref,
                context=draft.context,
                evidence=list(contribution.evidence),
                causal_refs=list(draft.causal_refs),
                retry_of=draft.retry_of,
                supersedes=draft.supersedes,
                failure_code=draft.failure_code,
            )
            self.by_id[record.id] = record
            self.by_key[record.idempotency_key] = record
            return record

    async def get(self, record_id: UUID) -> ActionRecord | None:
        return self.by_id.get(record_id)

    async def list(self, **_kwargs) -> list[ActionRecord]:
        return list(self.by_id.values())


async def test_idempotency_key_is_five_part() -> None:
    key = idempotency_key(
        producer_kind="workspace",
        source_record_type="run",
        source_record_id="abc",
        action_kind="shell",
        lifecycle=ActionLifecycle.SUCCEEDED,
    )
    assert key == "workspace:run:abc:shell:succeeded"


async def test_replay_converges_on_one_record() -> None:
    store = InMemoryActionRecordStore()
    recorder = ActionRecorder(store)
    kwargs = dict(
        producer_kind="workspace",
        source_record_type="run",
        source_record_id="run-1",
        action_kind="shell",
        lifecycle=ActionLifecycle.SUCCEEDED,
        outcome=ActionOutcome.SUCCESS,
        actor="workspace",
        producer_plugin="ze-workspace",
        occurred_at=datetime.now(timezone.utc),
        summary="workspace run succeeded",
        context=ActionContext(),
    )
    first = await recorder.record_action(**kwargs)
    second = await recorder.record_action(**kwargs)
    assert first.id == second.id
    assert len(store.by_key) == 1


async def test_terminal_is_causally_linked_to_started() -> None:
    store = InMemoryActionRecordStore()
    recorder = ActionRecorder(store)
    common = dict(
        producer_kind="workflow",
        source_record_type="workflow_execution",
        source_record_id="exec-1",
        action_kind="execute",
        actor="workflow_scheduler",
        producer_plugin="ze-automation",
        occurred_at=datetime.now(timezone.utc),
        context=ActionContext(),
    )
    started = await recorder.record_action(
        **common,
        lifecycle=ActionLifecycle.STARTED,
        outcome=None,
        summary="started",
        confidence_value=0.4,
    )
    finished = await recorder.record_action(
        **common,
        lifecycle=ActionLifecycle.SUCCEEDED,
        outcome=ActionOutcome.SUCCESS,
        summary="succeeded",
    )
    assert started.id != finished.id
    assert any(ref.id == started.id for ref in finished.causal_refs)
