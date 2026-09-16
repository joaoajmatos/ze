"""Append-only action_records ledger (Phase 135).

Revision ID: zm021
Revises: zm020
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zm021"
down_revision: Union[str, Sequence[str], None] = "zm020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE action_records (
            id UUID PRIMARY KEY,
            idempotency_key TEXT NOT NULL UNIQUE,
            action_type TEXT NOT NULL,
            actor TEXT NOT NULL,
            producer_plugin TEXT NOT NULL,
            lifecycle TEXT NOT NULL,
            outcome TEXT,
            occurred_at TIMESTAMPTZ NOT NULL,
            provenance TEXT NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            target_face TEXT NOT NULL,
            summary TEXT NOT NULL,
            authoritative_domain TEXT NOT NULL,
            authoritative_record_id TEXT NOT NULL,
            context JSONB NOT NULL DEFAULT '{}'::jsonb,
            evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
            causal_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            retry_of UUID REFERENCES action_records (id),
            supersedes UUID REFERENCES action_records (id),
            failure_code TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT action_records_lifecycle_check
              CHECK (lifecycle IN (
                'started', 'in_progress', 'succeeded', 'failed',
                'cancelled', 'partial', 'timed_out', 'unknown'
              )),
            CONSTRAINT action_records_outcome_check
              CHECK (outcome IS NULL OR outcome IN (
                'success', 'failure', 'cancelled', 'partial', 'timeout', 'unknown'
              )),
            CONSTRAINT action_records_outcome_terminal_check
              CHECK (
                (lifecycle IN ('started', 'in_progress') AND outcome IS NULL)
                OR (lifecycle NOT IN ('started', 'in_progress') AND outcome IS NOT NULL)
              ),
            CONSTRAINT action_records_provenance_doctrine
              CHECK (provenance IN (
                'graph_recall', 'live_search', 'prompt_supplied', 'synthesized'
              )),
            CONSTRAINT action_records_target_face_doctrine
              CHECK (target_face IN ('self', 'user', 'world', 'active_concerns')),
            CONSTRAINT action_records_confidence_range
              CHECK (confidence >= 0 AND confidence <= 1),
            CONSTRAINT action_records_retry_not_self
              CHECK (retry_of IS DISTINCT FROM id),
            CONSTRAINT action_records_supersedes_not_self
              CHECK (supersedes IS DISTINCT FROM id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX action_records_occurred_at_idx
            ON action_records (occurred_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX action_records_authoritative_idx
            ON action_records (
                authoritative_domain, authoritative_record_id, occurred_at DESC
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS action_records")
