"""Rename has_unsupported_scripts, add executable approval and skill_scripts.

Revision ID: zsk002
Revises: zsk001
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zsk002"
down_revision: Union[str, Sequence[str], None] = "zsk001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE skills RENAME COLUMN has_unsupported_scripts TO has_scripts"
    )
    op.execute(
        """
        ALTER TABLE skills
            ADD COLUMN IF NOT EXISTS executable_approved BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS executable_approved_at TIMESTAMPTZ NULL
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS skill_scripts (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            skill_id   UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
            filename   TEXT NOT NULL,
            content    BYTEA NOT NULL,
            UNIQUE (skill_id, filename)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS skill_scripts_skill_idx ON skill_scripts (skill_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS skill_scripts")
    op.execute(
        "ALTER TABLE skills DROP COLUMN IF EXISTS executable_approved_at"
    )
    op.execute("ALTER TABLE skills DROP COLUMN IF EXISTS executable_approved")
    op.execute(
        "ALTER TABLE skills RENAME COLUMN has_scripts TO has_unsupported_scripts"
    )
