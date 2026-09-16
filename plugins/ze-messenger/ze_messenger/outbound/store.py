from __future__ import annotations

from typing import Protocol
from uuid import UUID

from ze_agents.db import DBPool

from ze_messenger.outbound.types import OutboundSend, OutboundSendOutcome


def _from_row(row) -> OutboundSend:
    return OutboundSend(
        id=row["id"],
        message_id=row["message_id"],
        thread_id=row["thread_id"],
        channel_type=row["channel_type"],
        channel_id=row["channel_id"],
        sent_at=row["sent_at"],
        outcome=OutboundSendOutcome(row["outcome"]),
        failure_code=row["failure_code"],
        ledger_idempotency_key=row["ledger_idempotency_key"],
        ledger_pending=bool(row["ledger_pending"]),
    )


class OutboundSendStore(Protocol):
    async def insert(self, send: OutboundSend) -> OutboundSend: ...

    async def mark_ledger_handoff(
        self, send_id: UUID, *, key: str, pending: bool
    ) -> None: ...

    async def list_ledger_pending(self) -> list[OutboundSend]: ...


class PostgresOutboundSendStore:
    def __init__(self, pool: DBPool) -> None:
        self._pool = pool

    async def insert(self, send: OutboundSend) -> OutboundSend:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO messenger_outbound_sends (
                    id, message_id, thread_id, channel_type, channel_id,
                    sent_at, outcome, failure_code
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING *
                """,
                send.id,
                send.message_id,
                send.thread_id,
                send.channel_type,
                send.channel_id,
                send.sent_at,
                send.outcome.value,
                send.failure_code,
            )
        return _from_row(row)

    async def mark_ledger_handoff(
        self, send_id: UUID, *, key: str, pending: bool
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE messenger_outbound_sends
                   SET ledger_idempotency_key = $2, ledger_pending = $3
                 WHERE id = $1
                """,
                send_id,
                key,
                pending,
            )

    async def list_ledger_pending(self) -> list[OutboundSend]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM messenger_outbound_sends WHERE ledger_pending = true"
                " ORDER BY sent_at ASC"
            )
        return [_from_row(r) for r in rows]
