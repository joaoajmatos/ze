"""Rollback record on the retried message (Phase 180).

Revision ID: zc032
Revises: zc031
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zc032"
down_revision: Union[str, Sequence[str], None] = "zc031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS rollback JSONB NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS rollback")
