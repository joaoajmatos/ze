"""Record each inbound poll's outcome on the channel watermark row.

Governance reads the outcome to tell an expired token from a quiet inbox.

Revision ID: zc040
Revises: zc039
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zc040"
down_revision: Union[str, Sequence[str], None] = "zc039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE user_channel_watermarks
            ADD COLUMN IF NOT EXISTS last_outcome    TEXT NULL,
            ADD COLUMN IF NOT EXISTS last_outcome_at TIMESTAMPTZ NULL
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE user_channel_watermarks
            DROP COLUMN IF EXISTS last_outcome_at,
            DROP COLUMN IF EXISTS last_outcome
    """)
