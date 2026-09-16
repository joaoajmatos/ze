from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_agents.errors import UnlicensedClaimKindError
from ze_plugin.contribution import Contribution, SourceFunction, TargetFace

from ze_memory.action_records.contribution import submit_action_record
from ze_memory.action_records.errors import ActionRecordNotFoundError
from ze_memory.action_records.types import (
    ActionLifecycle,
    ActionOutcome,
    ActionRecord,
    ActionRecordDraft,
    AuthoritativeRef,
    CausalRef,
)


class InMemoryActionRecordStore:
    def __init__(self) -> None:
        self.by_id: dict[UUID, ActionRecord] = {}
        self.by_key: dict[str, ActionRecord] = {}
        self.lock = asyncio.Lock()
        self.append_calls = 0
        self.fail_next = False

    async def append(self, contribution: Contribution) -> ActionRecord:
        self.append_calls += 1
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("ledger unavailable")
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


def _confidence(value: float = 1.0) -> Confidence:
    return Confidence(value=value, decay_profile=DecayProfile.TIME_LINEAR)


def _draft(**overrides) -> ActionRecordDraft:
    base = dict(
        idempotency_key="key-1",
        action_type="workspace.run",
        actor="workspace",
        producer_plugin="ze-workspace",
        lifecycle=ActionLifecycle.SUCCEEDED,
        outcome=ActionOutcome.SUCCESS,
        occurred_at=datetime.now(timezone.utc),
        summary="workspace run succeeded",
        authoritative_ref=AuthoritativeRef(
            domain="workspace.runs", record_id=str(uuid4())
        ),
    )
    base.update(overrides)
    return ActionRecordDraft(**base)


def _contribution(draft: ActionRecordDraft, **overrides) -> Contribution:
    kwargs = dict(
        claim_kind=ClaimKind.ACTION_RECORD,
        provenance=Provenance.PROMPT_SUPPLIED,
        confidence=_confidence(),
        target_face=TargetFace.WORLD,
        source_function=SourceFunction.ACTION,
        action_record=draft,
    )
    kwargs.update(overrides)
    return Contribution(**kwargs)


async def test_submit_appends_one_action_record() -> None:
    store = InMemoryActionRecordStore()
    record = await submit_action_record(store, _contribution(_draft()))
    assert record.lifecycle is ActionLifecycle.SUCCEEDED
    assert store.append_calls == 1
    assert len(store.by_id) == 1


async def test_concurrent_same_key_returns_one_row() -> None:
    store = InMemoryActionRecordStore()
    contrib_a = _contribution(_draft())
    contrib_b = _contribution(_draft())
    first, second = await asyncio.gather(
        submit_action_record(store, contrib_a),
        submit_action_record(store, contrib_b),
    )
    assert first.id == second.id
    assert len(store.by_key) == 1


async def test_retry_appends_new_row() -> None:
    store = InMemoryActionRecordStore()
    original = await submit_action_record(store, _contribution(_draft()))
    retry = await submit_action_record(
        store,
        _contribution(
            _draft(
                idempotency_key="key-2",
                retry_of=original.id,
                summary="workspace run retry succeeded",
            )
        ),
    )
    assert retry.id != original.id
    assert retry.retry_of == original.id
    assert len(store.by_id) == 2


async def test_dangling_action_record_causal_ref_fails() -> None:
    store = InMemoryActionRecordStore()
    with pytest.raises(ActionRecordNotFoundError):
        await submit_action_record(
            store,
            _contribution(
                _draft(causal_refs=[CausalRef(kind="action_record", id=uuid4())])
            ),
        )


async def test_perception_cannot_submit_action_record() -> None:
    store = InMemoryActionRecordStore()
    with pytest.raises((UnlicensedClaimKindError, Exception)):
        await submit_action_record(
            store,
            _contribution(
                _draft(),
                source_function=SourceFunction.PERCEPTION,
                claim_kind=ClaimKind.FACT,
                action_record=None,
            ),
        )
