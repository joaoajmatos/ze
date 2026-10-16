"""Drop capability_overrides: the intent-based capability gate is gone (Phase 181).

Revision ID: zc034
Revises: zc033
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zc034"
down_revision: Union[str, Sequence[str], None] = "zc033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS capability_overrides")


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS capability_overrides (
            agent      TEXT        NOT NULL,
            intent     TEXT        NOT NULL,
            mode       TEXT        NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (agent, intent)
        )
        """
    )
