"""Durable outbound send citations for the ActionRecord ledger (Phase 135).

Revision ID: zmsg001
Revises:
Create Date: 2026-09-15
Branch labels: ze_messenger
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zmsg001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = ("ze_messenger",)
depends_on: Union[str, Sequence[str], None] = "zc001"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE messenger_outbound_sends (
            id UUID PRIMARY KEY,
            message_id TEXT NOT NULL,
            thread_id TEXT NOT NULL,
            channel_type TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            sent_at TIMESTAMPTZ NOT NULL,
            outcome TEXT NOT NULL,
            failure_code TEXT,
            ledger_idempotency_key TEXT,
            ledger_pending BOOLEAN NOT NULL DEFAULT false,
            CONSTRAINT messenger_outbound_sends_outcome_check
              CHECK (outcome IN ('success', 'failure', 'unknown'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX messenger_outbound_sends_message_id_idx
            ON messenger_outbound_sends (message_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS messenger_outbound_sends")
