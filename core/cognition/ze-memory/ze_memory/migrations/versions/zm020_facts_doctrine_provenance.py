"""Hard-cut memory_facts.provenance onto doctrine Provenance values.

Revision ID: zm020
Revises: zm019
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "zm020"
down_revision: Union[str, Sequence[str], None] = "zm019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ALLOWED_BEFORE = (
    "raw",
    "synthesized",
    "graph_recall",
    "live_search",
    "prompt_supplied",
)


def upgrade() -> None:
    conn = op.get_bind()
    unexpected = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM memory_facts
             WHERE provenance IS NOT NULL
               AND provenance NOT IN (
                 'raw', 'synthesized', 'graph_recall', 'live_search', 'prompt_supplied'
               )
            """
        )
    ).scalar()
    if unexpected:
        raise RuntimeError(
            f"memory_facts has {unexpected} row(s) with provenance outside "
            f"{_ALLOWED_BEFORE}; aborting zm020"
        )
    op.execute(
        """
        UPDATE memory_facts
           SET provenance = 'prompt_supplied'
         WHERE provenance IS NULL OR provenance = 'raw'
        """
    )
    op.execute("ALTER TABLE memory_facts ALTER COLUMN provenance DROP DEFAULT")
    op.execute("ALTER TABLE memory_facts ALTER COLUMN provenance SET NOT NULL")
    op.execute(
        """
        ALTER TABLE memory_facts ADD CONSTRAINT memory_facts_provenance_doctrine
          CHECK (provenance IN (
            'graph_recall', 'live_search', 'prompt_supplied', 'synthesized'
          ))
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE memory_facts DROP CONSTRAINT IF EXISTS memory_facts_provenance_doctrine"
    )
    op.execute("ALTER TABLE memory_facts ALTER COLUMN provenance SET DEFAULT 'raw'")
