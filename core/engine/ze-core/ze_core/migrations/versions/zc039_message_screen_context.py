"""Screen context stored on the user message so Retry replays it (Phase 195).

Revision ID: zc039
Revises: zc038
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zc039"
down_revision: Union[str, Sequence[str], None] = "zc038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS screen_context JSONB NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS screen_context")
