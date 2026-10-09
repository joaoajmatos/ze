from __future__ import annotations

from typing import Protocol
from uuid import UUID, uuid4

import asyncpg

from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_agents.db import DBPool
from ze_agents.errors import FeedbackRecordIdempotencyConflictError
from ze_logging import get_logger
from ze_plugin.contribution import Contribution, TargetFace

from ze_memory.errors import StoreError
from ze_memory.feedback_records.types import (
    FeedbackKind,
    FeedbackRecord,
    FeedbackRecordDraft,
    material_tuple,
    validate_draft,
)

log = get_logger(__name__)


class FeedbackStore(Protocol):
    async def append(self, contribution: Contribution) -> FeedbackRecord: ...

    async def latest_rating(self, message_id: UUID) -> FeedbackRecord | None: ...

    async def history(self, message_id: UUID) -> list[FeedbackRecord]: ...

    async def list_for_messages(
        self, message_ids: list[UUID]
    ) -> dict[UUID, list[FeedbackRecord]]: ...


def _record_from_row(row) -> FeedbackRecord:
    return FeedbackRecord(
        id=row["id"],
        idempotency_key=row["idempotency_key"],
        message_id=row["message_id"],
        thread_id=row["thread_id"],
        kind=FeedbackKind(row["kind"]),
        occurred_at=row["occurred_at"],
        provenance=Provenance(row["provenance"]),
        confidence=Confidence(
            value=float(row["confidence"]), decay_profile=DecayProfile.TIME_LINEAR
        ),
        target_face=TargetFace(row["target_face"]),
        trace_present=bool(row["trace_present"]),
        created_at=row["created_at"] if "created_at" in row.keys() else None,
    )


def _draft_from_record(record: FeedbackRecord) -> FeedbackRecordDraft:
    return FeedbackRecordDraft(
        idempotency_key=record.idempotency_key,
        message_id=record.message_id,
        thread_id=record.thread_id,
        kind=record.kind,
        occurred_at=record.occurred_at,
        trace_present=record.trace_present,
    )


_RATING_SQL = "kind IN ('thumbs_up', 'thumbs_down', 'cleared')"


class PostgresFeedbackStore:
    """Append-only ledger. No update or delete API; deletion belongs to the data domain."""

    def __init__(self, pool: DBPool) -> None:
        self._pool = pool

    async def append(self, contribution: Contribution) -> FeedbackRecord:
        if contribution.claim_kind is not ClaimKind.FEEDBACK_RECORD:
            raise StoreError("FeedbackStore.append requires FEEDBACK_RECORD")
        if contribution.feedback_record is None:
            raise StoreError("FeedbackStore.append requires feedback_record payload")
        draft = validate_draft(contribution.feedback_record)

        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO feedback_records (
                        id, idempotency_key, message_id, thread_id, kind,
                        occurred_at, provenance, confidence, target_face,
                        trace_present
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING *
                    """,
                    uuid4(),
                    draft.idempotency_key,
                    draft.message_id,
                    draft.thread_id,
                    draft.kind.value,
                    draft.occurred_at,
                    contribution.provenance.value,
                    contribution.confidence.value,
                    contribution.target_face.value,
                    draft.trace_present,
                )
            except asyncpg.UniqueViolationError:
                row = None
            if row is None:
                existing = await conn.fetchrow(
                    "SELECT * FROM feedback_records WHERE idempotency_key = $1",
                    draft.idempotency_key,
                )
                if existing is None:
                    raise StoreError(
                        f"idempotency conflict for {draft.idempotency_key} "
                        "but no existing row"
                    )
                record = _record_from_row(existing)
                if material_tuple(_draft_from_record(record)) != material_tuple(draft):
                    raise FeedbackRecordIdempotencyConflictError(
                        f"idempotency key {draft.idempotency_key!r} already "
                        "stores a different observation"
                    )
                log.info(
                    "feedback_record_idempotent_hit",
                    idempotency_key=draft.idempotency_key,
                    record_id=str(record.id),
                )
                return record
        record = _record_from_row(row)
        log.info(
            "feedback_record_appended",
            record_id=str(record.id),
            message_id=str(record.message_id),
            kind=record.kind.value,
        )
        return record

    async def latest_rating(self, message_id: UUID) -> FeedbackRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT * FROM feedback_records
                WHERE message_id = $1 AND {_RATING_SQL}
                ORDER BY occurred_at DESC, created_at DESC
                LIMIT 1
                """,
                message_id,
            )
        return _record_from_row(row) if row is not None else None

    async def history(self, message_id: UUID) -> list[FeedbackRecord]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM feedback_records
                WHERE message_id = $1
                ORDER BY occurred_at ASC, created_at ASC
                """,
                message_id,
            )
        return [_record_from_row(r) for r in rows]

    async def list_for_messages(
        self, message_ids: list[UUID]
    ) -> dict[UUID, list[FeedbackRecord]]:
        if not message_ids:
            return {}
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM feedback_records
                WHERE message_id = ANY($1::uuid[])
                ORDER BY occurred_at ASC, created_at ASC
                """,
                message_ids,
            )
        grouped: dict[UUID, list[FeedbackRecord]] = {}
        for row in rows:
            record = _record_from_row(row)
            grouped.setdefault(record.message_id, []).append(record)
        return grouped
