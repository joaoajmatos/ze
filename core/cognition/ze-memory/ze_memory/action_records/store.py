from __future__ import annotations

import json
from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

import asyncpg

from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_agents.db import DBPool
from ze_logging import get_logger
from ze_plugin.contribution import Contribution, EvidenceRef, TargetFace

from ze_memory.action_records.errors import (
    ActionRecordConflictError,
    ActionRecordNotFoundError,
)
from ze_memory.action_records.types import (
    ActionContext,
    ActionLifecycle,
    ActionOutcome,
    ActionRecord,
    ActionRecordDraft,
    AuthoritativeRef,
    CausalRef,
    material_tuple,
    validate_draft,
)
from ze_memory.errors import StoreError

log = get_logger(__name__)


class ActionRecordStore(Protocol):
    async def append(self, contribution: Contribution) -> ActionRecord: ...

    async def get(self, record_id: UUID) -> ActionRecord | None: ...

    async def list(
        self,
        *,
        authoritative_ref: AuthoritativeRef | None = None,
        causal_ref: CausalRef | None = None,
        before: datetime | None = None,
        limit: int = 100,
    ) -> list[ActionRecord]: ...


def _uuid_str(value: UUID | None) -> str | None:
    return None if value is None else str(value)


def _parse_uuid(value: str | UUID | None) -> UUID | None:
    if value is None:
        return None
    return value if isinstance(value, UUID) else UUID(str(value))


def _context_to_json(ctx: ActionContext) -> str:
    return json.dumps(
        {
            "request_id": _uuid_str(ctx.request_id),
            "session_id": _uuid_str(ctx.session_id),
            "message_id": _uuid_str(ctx.message_id),
            "thread_id": _uuid_str(ctx.thread_id),
            "goal_id": _uuid_str(ctx.goal_id),
            "milestone_id": _uuid_str(ctx.milestone_id),
            "workflow_id": _uuid_str(ctx.workflow_id),
            "workflow_run_id": _uuid_str(ctx.workflow_run_id),
            "workspace_run_id": _uuid_str(ctx.workspace_run_id),
            "channel_id": _uuid_str(ctx.channel_id),
            "outreach_id": _uuid_str(ctx.outreach_id),
            "calendar_ref": ctx.calendar_ref,
            "reminder_id": _uuid_str(ctx.reminder_id),
        }
    )


def _evidence_to_json(evidence: list[EvidenceRef]) -> str:
    return json.dumps([{"kind": ref.kind, "id": str(ref.id)} for ref in evidence])


def _causal_to_json(refs: list[CausalRef]) -> str:
    return json.dumps([{"kind": ref.kind, "id": str(ref.id)} for ref in refs])


def _load_json(raw) -> object:
    if raw is None:
        return None
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def _context_from_json(raw) -> ActionContext:
    data = _load_json(raw) or {}
    if not isinstance(data, dict):
        data = {}
    return ActionContext(
        request_id=_parse_uuid(data.get("request_id")),
        session_id=_parse_uuid(data.get("session_id")),
        message_id=_parse_uuid(data.get("message_id")),
        thread_id=_parse_uuid(data.get("thread_id")),
        goal_id=_parse_uuid(data.get("goal_id")),
        milestone_id=_parse_uuid(data.get("milestone_id")),
        workflow_id=_parse_uuid(data.get("workflow_id")),
        workflow_run_id=_parse_uuid(data.get("workflow_run_id")),
        workspace_run_id=_parse_uuid(data.get("workspace_run_id")),
        channel_id=_parse_uuid(data.get("channel_id")),
        outreach_id=_parse_uuid(data.get("outreach_id")),
        calendar_ref=data.get("calendar_ref"),
        reminder_id=_parse_uuid(data.get("reminder_id")),
    )


def _evidence_from_json(raw) -> list[EvidenceRef]:
    data = _load_json(raw) or []
    return [EvidenceRef(kind=item["kind"], id=UUID(str(item["id"]))) for item in data]


def _causal_from_json(raw) -> list[CausalRef]:
    data = _load_json(raw) or []
    refs: list[CausalRef] = []
    for item in data:
        raw_id = item["id"]
        kind = item["kind"]
        parsed: UUID | str
        if kind == "action_record":
            parsed = UUID(str(raw_id))
        else:
            try:
                parsed = UUID(str(raw_id))
            except ValueError:
                parsed = str(raw_id)
        refs.append(CausalRef(kind=kind, id=parsed))
    return refs


def _record_from_row(row) -> ActionRecord:
    outcome_raw = row["outcome"]
    return ActionRecord(
        id=row["id"],
        idempotency_key=row["idempotency_key"],
        action_type=row["action_type"],
        actor=row["actor"],
        producer_plugin=row["producer_plugin"],
        lifecycle=ActionLifecycle(row["lifecycle"]),
        outcome=ActionOutcome(outcome_raw) if outcome_raw is not None else None,
        occurred_at=row["occurred_at"],
        provenance=Provenance(row["provenance"]),
        confidence=Confidence(
            value=float(row["confidence"]),
            decay_profile=DecayProfile.TIME_LINEAR,
        ),
        target_face=TargetFace(row["target_face"]),
        summary=row["summary"],
        authoritative_ref=AuthoritativeRef(
            domain=row["authoritative_domain"],
            record_id=row["authoritative_record_id"],
        ),
        context=_context_from_json(row["context"]),
        evidence=_evidence_from_json(row["evidence"]),
        causal_refs=_causal_from_json(row["causal_refs"]),
        retry_of=row["retry_of"],
        supersedes=row["supersedes"],
        failure_code=row["failure_code"],
        created_at=row["created_at"] if "created_at" in row.keys() else None,
    )


def draft_from_record(record: ActionRecord) -> ActionRecordDraft:
    return ActionRecordDraft(
        idempotency_key=record.idempotency_key,
        action_type=record.action_type,
        actor=record.actor,
        producer_plugin=record.producer_plugin,
        lifecycle=record.lifecycle,
        outcome=record.outcome,
        occurred_at=record.occurred_at,
        summary=record.summary,
        authoritative_ref=record.authoritative_ref,
        context=record.context,
        causal_refs=list(record.causal_refs),
        retry_of=record.retry_of,
        supersedes=record.supersedes,
        failure_code=record.failure_code,
    )


class PostgresActionRecordStore:
    def __init__(self, pool: DBPool) -> None:
        self._pool = pool

    async def append(self, contribution: Contribution) -> ActionRecord:
        if contribution.claim_kind is not ClaimKind.ACTION_RECORD:
            raise StoreError("ActionRecordStore.append requires ACTION_RECORD")
        if contribution.action_record is None:
            raise StoreError("ActionRecordStore.append requires action_record payload")
        draft = validate_draft(contribution.action_record)
        if draft.retry_of is not None and await self.get(draft.retry_of) is None:
            raise ActionRecordNotFoundError(f"retry_of {draft.retry_of} does not exist")
        if draft.supersedes is not None and await self.get(draft.supersedes) is None:
            raise ActionRecordNotFoundError(
                f"supersedes {draft.supersedes} does not exist"
            )
        for ref in draft.causal_refs:
            if ref.kind == "action_record":
                cited = ref.id if isinstance(ref.id, UUID) else UUID(str(ref.id))
                if await self.get(cited) is None:
                    raise ActionRecordNotFoundError(
                        f"causal action_record {cited} does not exist"
                    )

        record_id = uuid4()
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO action_records (
                        id, idempotency_key, action_type, actor, producer_plugin,
                        lifecycle, outcome, occurred_at, provenance, confidence,
                        target_face, summary, authoritative_domain,
                        authoritative_record_id, context, evidence, causal_refs,
                        retry_of, supersedes, failure_code
                    ) VALUES (
                        $1, $2, $3, $4, $5,
                        $6, $7, $8, $9, $10,
                        $11, $12, $13,
                        $14, $15::jsonb, $16::jsonb, $17::jsonb,
                        $18, $19, $20
                    )
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING *
                    """,
                    record_id,
                    draft.idempotency_key,
                    draft.action_type,
                    draft.actor,
                    draft.producer_plugin,
                    draft.lifecycle.value,
                    None if draft.outcome is None else draft.outcome.value,
                    draft.occurred_at,
                    contribution.provenance.value,
                    contribution.confidence.value,
                    contribution.target_face.value,
                    draft.summary,
                    draft.authoritative_ref.domain,
                    draft.authoritative_ref.record_id,
                    _context_to_json(draft.context),
                    _evidence_to_json(contribution.evidence),
                    _causal_to_json(draft.causal_refs),
                    draft.retry_of,
                    draft.supersedes,
                    draft.failure_code,
                )
            except asyncpg.UniqueViolationError:
                row = None
            if row is None:
                existing = await conn.fetchrow(
                    "SELECT * FROM action_records WHERE idempotency_key = $1",
                    draft.idempotency_key,
                )
                if existing is None:
                    raise StoreError(
                        f"idempotency conflict for {draft.idempotency_key} "
                        "but no existing row"
                    )
                record = _record_from_row(existing)
                if material_tuple(draft_from_record(record)) != material_tuple(draft):
                    raise ActionRecordConflictError(
                        f"idempotency key {draft.idempotency_key!r} already "
                        "stores a different observation"
                    )
                log.info(
                    "action_record_idempotent_hit",
                    idempotency_key=draft.idempotency_key,
                    record_id=str(record.id),
                )
                return record
        record = _record_from_row(row)
        log.info(
            "action_record_appended",
            record_id=str(record.id),
            action_type=record.action_type,
            lifecycle=record.lifecycle.value,
            producer_plugin=record.producer_plugin,
        )
        return record

    async def get(self, record_id: UUID) -> ActionRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM action_records WHERE id = $1", record_id
            )
        return _record_from_row(row) if row is not None else None

    async def list(
        self,
        *,
        authoritative_ref: AuthoritativeRef | None = None,
        causal_ref: CausalRef | None = None,
        before: datetime | None = None,
        limit: int = 100,
    ) -> list[ActionRecord]:
        clauses: list[str] = []
        args: list[object] = []

        def _add(clause: str, value: object) -> None:
            args.append(value)
            clauses.append(clause.replace("?", f"${len(args)}"))

        if authoritative_ref is not None:
            _add("authoritative_domain = ?", authoritative_ref.domain)
            _add("authoritative_record_id = ?", authoritative_ref.record_id)
        if causal_ref is not None:
            payload = json.dumps([{"kind": causal_ref.kind, "id": str(causal_ref.id)}])
            _add("causal_refs @> ?::jsonb", payload)
        if before is not None:
            _add("occurred_at < ?", before)
        args.append(max(1, min(limit, 500)))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            f"SELECT * FROM action_records {where} "
            f"ORDER BY occurred_at DESC, created_at DESC LIMIT ${len(args)}"
        )
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
        return [_record_from_row(row) for row in rows]
