"""Add provenance to memory_signals (Contribution Seam Core, FR-002).

Revision ID: zm018
Revises: zm017
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zm018"
down_revision: Union[str, Sequence[str], None] = "zm017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE memory_signals ADD COLUMN provenance TEXT")
    op.execute(
        "UPDATE memory_signals SET provenance = 'synthesized' WHERE provenance IS NULL"
    )
    op.execute("ALTER TABLE memory_signals ALTER COLUMN provenance SET NOT NULL")
    op.execute("ALTER TABLE memory_signals ALTER COLUMN provenance DROP DEFAULT")


def downgrade() -> None:
    op.execute("ALTER TABLE memory_signals DROP COLUMN provenance")
