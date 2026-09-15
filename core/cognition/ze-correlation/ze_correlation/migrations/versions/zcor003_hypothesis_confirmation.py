"""Add confirmed/promoted_at to correlation_hypothesis.

Revision ID: zcor003
Revises: zcor002
"""

from __future__ import annotations
from typing import Sequence, Union
from alembic import op

revision: str = "zcor003"
down_revision: Union[str, Sequence[str], None] = "zcor002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE correlation_hypothesis"
        " ADD COLUMN IF NOT EXISTS confirmed BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE correlation_hypothesis"
        " ADD COLUMN IF NOT EXISTS promoted_at TIMESTAMPTZ NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE correlation_hypothesis DROP COLUMN IF EXISTS promoted_at"
    )
    op.execute(
        "ALTER TABLE correlation_hypothesis DROP COLUMN IF EXISTS confirmed"
    )
