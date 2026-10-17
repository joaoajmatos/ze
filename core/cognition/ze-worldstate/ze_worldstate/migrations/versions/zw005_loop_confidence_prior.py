"""Add open_loops.confidence_prior and confidence_changed_at (Phase 185).

The value before the last confidence change, and when it changed. Nullable and
never back-filled: a loop whose confidence never changed has neither.

Revision ID: zw005
Revises: zw004
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zw005"
down_revision: Union[str, Sequence[str], None] = "zw004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE open_loops "
        "ADD COLUMN IF NOT EXISTS confidence_prior REAL NULL, "
        "ADD COLUMN IF NOT EXISTS confidence_changed_at TIMESTAMPTZ NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE open_loops "
        "DROP COLUMN IF EXISTS confidence_prior, "
        "DROP COLUMN IF EXISTS confidence_changed_at"
    )
