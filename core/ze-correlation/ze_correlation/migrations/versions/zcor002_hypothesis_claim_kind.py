"""Add claim_kind to correlation_hypothesis.

Revision ID: zcor002
Revises: zcor001
"""

from __future__ import annotations
from typing import Sequence, Union
from alembic import op

revision: str = "zcor002"
down_revision: Union[str, Sequence[str], None] = "zcor001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE correlation_hypothesis ADD COLUMN IF NOT EXISTS claim_kind TEXT")
    op.execute(
        "UPDATE correlation_hypothesis SET claim_kind = 'inference' WHERE claim_kind IS NULL"
    )
    op.execute("ALTER TABLE correlation_hypothesis ALTER COLUMN claim_kind SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE correlation_hypothesis DROP COLUMN IF EXISTS claim_kind")
