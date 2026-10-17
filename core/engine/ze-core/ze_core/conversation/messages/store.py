from __future__ import annotations

import json
from dataclasses import asdict, fields
from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg

from ze_logging import get_logger

from ze_core.conversation.messages.types import (
    CompactionTrace,
    JudgmentTrace,
    Message,
    MessageTrace,
    MemoryChunkTrace,
    RollbackRecord,
    RollbackTrace,
    ProcedureUsageTrace,
    SkillUsageTrace,
    SourceTrace,
    ScreenTrace,
    TierTrace,
    ToolCallTrace,
    WorkspaceUsageTrace,
)


log = get_logger(__name__)


class MessageStore(Protocol):
    async def save(self, message: Message) -> None: ...
    async def list_since(
        self, since: datetime, limit: int = 100, *, include_superseded: bool = False
    ) -> list[Message]: ...
    async def list_by_thread(
        self, thread_id: str, limit: int = 200, *, include_superseded: bool = False
    ) -> list[Message]: ...
    async def mark_read(self, ids: list[UUID]) -> None: ...
    async def list_unread(
        self, thread_id: str | None = None, *, include_superseded: bool = False
    ) -> list[Message]: ...
    async def get_message(self, message_id: UUID) -> Message | None: ...
    async def get_messages(self, message_ids: list[UUID]) -> dict[UUID, Message]: ...
    async def latest_assistant_id(self, thread_id: str) -> UUID | None: ...
    async def previous_user_message(self, message_id: UUID) -> Message | None: ...
    async def mark_superseded(self, old_id: UUID, new_id: UUID) -> bool: ...
    async def set_rollback(self, message_id: UUID, record: RollbackRecord) -> None: ...
    async def save_trace(self, message_id: UUID, trace: MessageTrace) -> None: ...
    async def get_trace(self, message_id: UUID) -> MessageTrace | None: ...
    async def get_traces(self, message_ids: list[UUID]) -> dict[UUID, MessageTrace]: ...


class PostgresMessageStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save(self, message: Message) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO messages (
                    id, role, text, components, read, thread_id, created_at, replaces,
                    screen_context
                )
                VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9::jsonb)
                ON CONFLICT DO NOTHING
                """,
                message.id,
                message.role,
                message.text,
                json.dumps(message.components),
                message.read,
                message.thread_id,
                message.created_at,
                message.replaces,
                json.dumps(message.screen_context)
                if message.screen_context is not None
                else None,
            )

    async def list_since(
        self, since: datetime, limit: int = 100, *, include_superseded: bool = False
    ) -> list[Message]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, role, text, components, read, thread_id, created_at,
                       replaces, replaced_by, rollback, screen_context
                FROM messages
                WHERE created_at > $1 AND ($3 OR replaced_by IS NULL)
                ORDER BY created_at ASC
                LIMIT $2
                """,
                since,
                limit,
                include_superseded,
            )
        return [_row_to_message(r) for r in rows]

    async def list_by_thread(
        self, thread_id: str, limit: int = 200, *, include_superseded: bool = False
    ) -> list[Message]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, role, text, components, read, thread_id, created_at,
                       replaces, replaced_by, rollback, screen_context
                FROM messages
                WHERE thread_id = $1 AND ($3 OR replaced_by IS NULL)
                ORDER BY created_at ASC
                LIMIT $2
                """,
                thread_id,
                limit,
                include_superseded,
            )
        return [_row_to_message(r) for r in rows]

    async def mark_read(self, ids: list[UUID]) -> None:
        if not ids:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE messages SET read = TRUE WHERE id = ANY($1)",
                ids,
            )

    async def list_unread(
        self, thread_id: str | None = None, *, include_superseded: bool = False
    ) -> list[Message]:
        async with self._pool.acquire() as conn:
            if thread_id:
                rows = await conn.fetch(
                    """
                    SELECT id, role, text, components, read, thread_id, created_at,
                       replaces, replaced_by, rollback, screen_context
                    FROM messages
                    WHERE NOT read AND thread_id = $1 AND ($2 OR replaced_by IS NULL)
                    ORDER BY created_at ASC
                    """,
                    thread_id,
                    include_superseded,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, role, text, components, read, thread_id, created_at,
                       replaces, replaced_by, rollback, screen_context
                    FROM messages
                    WHERE NOT read AND ($1 OR replaced_by IS NULL)
                    ORDER BY created_at ASC
                    """,
                    include_superseded,
                )
        return [_row_to_message(r) for r in rows]

    async def get_message(self, message_id: UUID) -> Message | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, role, text, components, read, thread_id, created_at,
                       replaces, replaced_by, rollback, screen_context
                FROM messages
                WHERE id = $1
                """,
                message_id,
            )
        return _row_to_message(row) if row is not None else None

    async def get_messages(self, message_ids: list[UUID]) -> dict[UUID, Message]:
        if not message_ids:
            return {}
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, role, text, components, read, thread_id, created_at,
                       replaces, replaced_by, rollback, screen_context
                FROM messages
                WHERE id = ANY($1::uuid[])
                """,
                message_ids,
            )
        return {r["id"]: _row_to_message(r) for r in rows}

    async def latest_assistant_id(self, thread_id: str) -> UUID | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id FROM messages
                WHERE thread_id = $1 AND role = 'assistant' AND replaced_by IS NULL
                ORDER BY created_at DESC
                LIMIT 1
                """,
                thread_id,
            )
        return row["id"] if row is not None else None

    async def previous_user_message(self, message_id: UUID) -> Message | None:
        """The user message a reply answers: the latest one before it in its thread."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT u.id, u.role, u.text, u.components, u.read, u.thread_id,
                       u.created_at, u.replaces, u.replaced_by, u.rollback,
                       u.screen_context
                FROM messages a
                JOIN messages u
                  ON u.thread_id = a.thread_id
                 AND u.role = 'user'
                 AND u.created_at < a.created_at
                WHERE a.id = $1
                ORDER BY u.created_at DESC
                LIMIT 1
                """,
                message_id,
            )
        return _row_to_message(row) if row is not None else None

    async def set_rollback(self, message_id: UUID, record: RollbackRecord) -> None:
        """Overwrite the rollback record; written after each undo so a crash stays honest."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE messages SET rollback = $1::jsonb WHERE id = $2",
                asdict(record),
                message_id,
            )

    async def mark_superseded(self, old_id: UUID, new_id: UUID) -> bool:
        """Link old to its replacement; only once the replacement is stored."""
        async with self._pool.acquire() as conn:
            status = await conn.execute(
                """
                UPDATE messages SET replaced_by = $2
                WHERE id = $1 AND replaced_by IS NULL
                  AND EXISTS (SELECT 1 FROM messages WHERE id = $2)
                """,
                old_id,
                new_id,
            )
        return status == "UPDATE 1"

    async def save_trace(self, message_id: UUID, trace: MessageTrace) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE messages SET trace = $1::jsonb WHERE id = $2",
                asdict(trace),
                message_id,
            )

    async def get_trace(self, message_id: UUID) -> MessageTrace | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT trace FROM messages WHERE id = $1", message_id
            )
        if row is None or row["trace"] is None:
            return None
        data = row["trace"]
        if isinstance(data, str):
            data = json.loads(data)
        return _parse_trace(data)

    async def get_traces(self, message_ids: list[UUID]) -> dict[UUID, MessageTrace]:
        if not message_ids:
            return {}
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, trace
                FROM messages
                WHERE id = ANY($1::uuid[]) AND trace IS NOT NULL
                """,
                message_ids,
            )
        result: dict[UUID, MessageTrace] = {}
        for row in rows:
            data = row["trace"]
            if isinstance(data, str):
                data = json.loads(data)
            result[row["id"]] = _parse_trace(data)
        return result


def _parse_trace(data: dict) -> MessageTrace:
    workspace_raw = data.get("workspace")
    workspace = None
    if workspace_raw:
        allowed = {f.name for f in fields(WorkspaceUsageTrace)}
        workspace = WorkspaceUsageTrace(
            **{k: v for k, v in workspace_raw.items() if k in allowed}
        )
    procedure_raw = data.get("procedure")
    procedure = ProcedureUsageTrace(**procedure_raw) if procedure_raw else None
    judgment_fields = {f.name for f in fields(JudgmentTrace)}
    tool_call_fields = {f.name for f in fields(ToolCallTrace)}
    return MessageTrace(
        agent=data["agent"],
        routing_method=data["routing_method"],
        confidence=data["confidence"],
        score_gap=data["score_gap"],
        is_compound=data["is_compound"],
        subtasks=data.get("subtasks", []),
        memory_chunks=[MemoryChunkTrace(**c) for c in data.get("memory_chunks", [])],
        tool_calls=[
            ToolCallTrace(**{k: v for k, v in t.items() if k in tool_call_fields})
            for t in data.get("tool_calls", [])
        ],
        total_duration_ms=data.get("total_duration_ms", 0),
        skills_used=[SkillUsageTrace(**s) for s in data.get("skills_used", [])],
        workspace=workspace,
        procedure=procedure,
        conductor_hint=data.get("conductor_hint"),
        conductor_ledger=list(data.get("conductor_ledger") or []),
        judgments=[
            JudgmentTrace(**{k: v for k, v in raw.items() if k in judgment_fields})
            for raw in data.get("judgments") or []
            if isinstance(raw, dict)
        ],
        sources=[
            SourceTrace(url=raw["url"], title=raw.get("title", ""))
            for raw in data.get("sources") or []
            if isinstance(raw, dict) and raw.get("url")
        ],
        effects_known=bool(data.get("effects_known", False)),
        compaction=CompactionTrace(**data["compaction"])
        if data.get("compaction")
        else None,
        resume_recap_applied=bool(data.get("resume_recap_applied", False)),
        rollback=RollbackTrace.from_dict(data["rollback"])
        if data.get("rollback")
        else None,
        loop_offer_ids=list(data.get("loop_offer_ids") or []),
        write_confirmations=[
            dict(row)
            for row in data.get("write_confirmations") or []
            if isinstance(row, dict)
        ],
        tier=TierTrace(**data["tier"]) if data.get("tier") else None,
        screen=ScreenTrace.from_dict(data["screen"])
        if isinstance(data.get("screen"), dict)
        else None,
    )


def _row_to_message(row: asyncpg.Record) -> Message:
    components = row["components"]
    if isinstance(components, str):
        components = json.loads(components)
    elif components is None:
        components = []
    return Message(
        id=row["id"],
        role=row["role"],
        text=row["text"],
        components=components,
        read=row["read"],
        thread_id=row["thread_id"],
        created_at=row["created_at"],
        replaces=row["replaces"],
        replaced_by=row["replaced_by"],
        rollback=_parse_rollback(row["rollback"]),
        screen_context=_parse_screen_context(row["screen_context"]),
    )


def _parse_screen_context(raw: object) -> dict | None:
    if raw is None:
        return None
    try:
        if isinstance(raw, str):
            raw = json.loads(raw)
    except ValueError:
        log.warning("screen_context_unreadable")
        return None
    return raw if isinstance(raw, dict) else None


def _parse_rollback(raw: object) -> RollbackRecord | None:
    if raw is None:
        return None
    try:
        if isinstance(raw, str):
            raw = json.loads(raw)
        return RollbackRecord.from_dict(raw) if raw else None
    except (TypeError, ValueError, KeyError, AttributeError):
        # One bad row must not break loading a whole thread.
        log.warning("rollback_record_unreadable")
        return None
