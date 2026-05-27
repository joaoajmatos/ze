"""Add capability_overrides table for persistent API mode changes

Revision ID: 017
Revises: 016
Create Date: 2026-05-27
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "017"
down_revision: Union[str, Sequence[str], None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS capability_overrides")
