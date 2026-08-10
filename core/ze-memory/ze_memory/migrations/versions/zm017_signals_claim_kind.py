"""Add claim_kind and confidence to memory_signals (Claim Topology, FR-012).

Revision ID: zm017
Revises: zm016
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zm017"
down_revision: Union[str, Sequence[str], None] = "zm016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE memory_signals ADD COLUMN claim_kind TEXT")
    op.execute("UPDATE memory_signals SET claim_kind = 'fact' WHERE claim_kind IS NULL")
    op.execute("ALTER TABLE memory_signals ALTER COLUMN claim_kind SET NOT NULL")

    op.execute("ALTER TABLE memory_signals ADD COLUMN confidence DOUBLE PRECISION")
    op.execute("UPDATE memory_signals SET confidence = 1.0 WHERE confidence IS NULL")
    op.execute("ALTER TABLE memory_signals ALTER COLUMN confidence SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE memory_signals DROP COLUMN confidence")
    op.execute("ALTER TABLE memory_signals DROP COLUMN claim_kind")
