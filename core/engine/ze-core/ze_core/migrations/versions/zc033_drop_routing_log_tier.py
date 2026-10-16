"""Drop the route-time tier from routing_log (Phase 182).

Revision ID: zc033
Revises: zc032
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zc033"
down_revision: Union[str, Sequence[str], None] = "zc032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE routing_log "
        "DROP COLUMN IF EXISTS complexity, "
        "DROP COLUMN IF EXISTS model_selected"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE routing_log "
        "ADD COLUMN IF NOT EXISTS complexity TEXT NULL, "
        "ADD COLUMN IF NOT EXISTS model_selected TEXT NULL"
    )
