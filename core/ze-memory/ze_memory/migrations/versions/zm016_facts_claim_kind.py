"""Add claim_kind to memory_facts (Claim Topology, FR-010).

Revision ID: zm016
Revises: zm015
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zm016"
down_revision: Union[str, Sequence[str], None] = "zm015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE memory_facts ADD COLUMN claim_kind TEXT")
    op.execute("""
        UPDATE memory_facts SET claim_kind = 'fact'
            WHERE claim_kind IS NULL AND (provenance != 'synthesized' OR corroborated = true)
    """)
    op.execute("""
        UPDATE memory_facts SET claim_kind = 'inference'
            WHERE claim_kind IS NULL AND provenance = 'synthesized' AND corroborated = false
    """)
    op.execute("ALTER TABLE memory_facts ALTER COLUMN claim_kind SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE memory_facts DROP COLUMN claim_kind")
