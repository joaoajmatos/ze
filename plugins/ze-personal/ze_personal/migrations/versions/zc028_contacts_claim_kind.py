"""Add claim_kind and provenance to contacts, contact_sources, contact_relationships
(Contribution Seam Extension, FR-006).

Revision ID: zc028
Revises: zc027
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zc028"
down_revision: Union[str, Sequence[str], None] = "zc027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROVENANCE_BACKFILL = """
    UPDATE {table} SET provenance = CASE source_type
        WHEN 'manual' THEN 'prompt_supplied'
        WHEN 'conversation' THEN 'synthesized'
        WHEN 'email' THEN 'live_search'
        WHEN 'calendar' THEN 'live_search'
        WHEN 'research' THEN 'synthesized'
        ELSE 'synthesized'
    END
"""


def upgrade() -> None:
    for table in ("contacts", "contact_sources", "contact_relationships"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN claim_kind TEXT")
        op.execute(f"UPDATE {table} SET claim_kind = 'identity'")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN claim_kind SET NOT NULL")

        op.execute(f"ALTER TABLE {table} ADD COLUMN provenance TEXT")
        op.execute(_PROVENANCE_BACKFILL.format(table=table))
        op.execute(f"ALTER TABLE {table} ALTER COLUMN provenance SET NOT NULL")


def downgrade() -> None:
    for table in ("contacts", "contact_sources", "contact_relationships"):
        op.execute(f"ALTER TABLE {table} DROP COLUMN provenance")
        op.execute(f"ALTER TABLE {table} DROP COLUMN claim_kind")
