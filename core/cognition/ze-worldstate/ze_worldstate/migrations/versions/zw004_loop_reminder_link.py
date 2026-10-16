"""Add open_loops.reminder_id: a loop can point at the reminder the turn created (Phase 173).

No foreign key: reminders belong to ze-calendar. goal_id already exists.

Revision ID: zw004
Revises: zw003
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zw004"
down_revision: Union[str, Sequence[str], None] = "zw003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE open_loops ADD COLUMN IF NOT EXISTS reminder_id UUID NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE open_loops DROP COLUMN IF EXISTS reminder_id")
