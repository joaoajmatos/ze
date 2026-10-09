"""Message supersession links for reply retry (Phase 165).

Revision ID: zc031
Revises: zc030
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zc031"
down_revision: Union[str, Sequence[str], None] = "zc030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS replaces UUID NULL")
    op.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS replaced_by UUID NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS messages_replaces_idx "
        "ON messages (replaces) WHERE replaces IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS messages_replaced_by_idx "
        "ON messages (replaced_by) WHERE replaced_by IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS replaced_by")
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS replaces")
