"""Append-only feedback_records evidence ledger (Phase 165).

Revision ID: zm024
Revises: zm023
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zm024"
down_revision: Union[str, Sequence[str], None] = "zm023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE feedback_records (
            id UUID PRIMARY KEY,
            idempotency_key TEXT NOT NULL UNIQUE,
            message_id UUID NOT NULL,
            thread_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            occurred_at TIMESTAMPTZ NOT NULL,
            provenance TEXT NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            target_face TEXT NOT NULL,
            trace_present BOOLEAN NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT feedback_records_kind_check
              CHECK (kind IN (
                'thumbs_up', 'thumbs_down', 'cleared', 'retry_requested'
              )),
            CONSTRAINT feedback_records_provenance_doctrine
              CHECK (provenance IN (
                'graph_recall', 'live_search', 'prompt_supplied', 'synthesized'
              )),
            CONSTRAINT feedback_records_target_face_doctrine
              CHECK (target_face IN ('self', 'user', 'world', 'active_concerns')),
            CONSTRAINT feedback_records_confidence_range
              CHECK (confidence >= 0 AND confidence <= 1)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX feedback_records_message_idx
            ON feedback_records (message_id, occurred_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX feedback_records_thread_idx
            ON feedback_records (thread_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS feedback_records")
