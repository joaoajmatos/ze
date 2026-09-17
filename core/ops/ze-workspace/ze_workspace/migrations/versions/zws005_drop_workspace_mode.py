"""Drop workspace_state.mode (Phase 161 — no execution modes).

Revision ID: zws005
Revises: zws004
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zws005"
down_revision: Union[str, Sequence[str], None] = "zws004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = "zws004"


def upgrade() -> None:
    op.execute("ALTER TABLE workspace_state DROP COLUMN IF EXISTS mode")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE workspace_state ADD COLUMN IF NOT EXISTS mode "
        "TEXT NOT NULL DEFAULT 'ask'"
    )
