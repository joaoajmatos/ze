"""Add open_loop_sources: each loop's origin and counted corroborations (Phase 172).

Revision ID: zw003
Revises: zw002
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zw003"
down_revision: Union[str, Sequence[str], None] = "zw002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS open_loop_sources (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          loop_id UUID NOT NULL REFERENCES open_loops(id) ON DELETE CASCADE,
          role TEXT NOT NULL CHECK (role IN ('origin', 'corroboration')),
          inflow TEXT NOT NULL,
          source_ref TEXT NOT NULL,
          evidence_kind TEXT NULL,
          evidence_id UUID NULL,
          same_concern DOUBLE PRECISION NULL,
          promoted BOOLEAN NOT NULL DEFAULT false,
          model TEXT NULL,
          latency_ms INTEGER NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (loop_id, inflow, source_ref)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS open_loop_sources_loop_idx"
        " ON open_loop_sources (loop_id, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS open_loop_sources_key_idx"
        " ON open_loop_sources (inflow, source_ref)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS open_loop_sources")
