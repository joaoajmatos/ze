"""Add last_contact to memory_relationships (Social Cognition Foundation, FR-005).

Revision ID: zm019
Revises: zm018
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zm019"
down_revision: Union[str, Sequence[str], None] = "zm018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE memory_relationships ADD COLUMN last_contact TIMESTAMPTZ")
    op.execute(
        "UPDATE memory_relationships SET last_contact = created_at WHERE last_contact IS NULL"
    )
    op.execute(
        "ALTER TABLE memory_relationships ALTER COLUMN last_contact SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE memory_relationships ALTER COLUMN last_contact SET DEFAULT now()"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE memory_relationships DROP COLUMN last_contact")
