"""Add persona_state table for runtime profile + dial persistence

Revision ID: 012
Revises: 011
Create Date: 2026-05-23
"""
from typing import Sequence, Union

from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS persona_state (
            id         SMALLINT    PRIMARY KEY DEFAULT 1
                       CONSTRAINT single_row CHECK (id = 1),
            profile    TEXT        NOT NULL DEFAULT 'default',
            dials      JSONB       NOT NULL DEFAULT '{}',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        INSERT INTO persona_state (id) VALUES (1) ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS persona_state")
