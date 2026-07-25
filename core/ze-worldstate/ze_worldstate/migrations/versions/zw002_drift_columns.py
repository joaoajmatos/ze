"""Add drift_deadline, drift_rationale columns to open_loops (Phase 110).

Revision ID: zw002
Revises: zw001
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zw002"
down_revision: Union[str, Sequence[str], None] = "zw001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE open_loops
          ADD COLUMN IF NOT EXISTS drift_deadline TIMESTAMPTZ NULL,
          ADD COLUMN IF NOT EXISTS drift_rationale TEXT NULL
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS open_loops_drift_deadline_idx"
        " ON open_loops (drift_deadline) WHERE state = 'active'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS open_loops_drift_deadline_idx")
    op.execute(
        """
        ALTER TABLE open_loops
          DROP COLUMN IF EXISTS drift_deadline,
          DROP COLUMN IF EXISTS drift_rationale
        """
    )
