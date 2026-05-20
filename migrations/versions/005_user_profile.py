"""Add user_profile table for Phase 6 profile synthesis

Revision ID: 005
Revises: 004
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id            SERIAL PRIMARY KEY,
            preferences   TEXT NOT NULL DEFAULT '',
            habits        TEXT NOT NULL DEFAULT '',
            topics        TEXT NOT NULL DEFAULT '',
            relationships TEXT NOT NULL DEFAULT '',
            goals         TEXT NOT NULL DEFAULT '',
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            version       INTEGER NOT NULL DEFAULT 0
        )
    """)
    op.execute("INSERT INTO user_profile DEFAULT VALUES")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_profile")
