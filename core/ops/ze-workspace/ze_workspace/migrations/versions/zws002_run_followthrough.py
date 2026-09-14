"""Add follow_through_notified to workspace_runs; allow in-progress rows (Phase 116).

Revision ID: zws002
Revises: zws001
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zws002"
down_revision: Union[str, Sequence[str], None] = "zws001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = "zws001"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE workspace_runs"
        " ADD COLUMN IF NOT EXISTS follow_through_notified BOOLEAN NOT NULL DEFAULT false"
    )
    # A detached run is inserted before its terminal status is known — status is
    # NULL only while ended_at is NULL (in progress); every terminal row still
    # carries one of WorkspaceRunStatus's five values, unchanged from Phase 115.
    op.execute("ALTER TABLE workspace_runs ALTER COLUMN status DROP NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE workspace_runs ALTER COLUMN status SET NOT NULL")
    op.execute("ALTER TABLE workspace_runs DROP COLUMN IF EXISTS follow_through_notified")
