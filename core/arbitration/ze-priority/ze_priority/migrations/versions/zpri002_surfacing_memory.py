"""Add surfacing_memory table — what the conversation already raised (Phase 204).

Revision ID: zpri002
Revises: zpri001
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zpri002"
down_revision: Union[str, Sequence[str], None] = "zpri001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS surfacing_memory (
            id          BIGSERIAL PRIMARY KEY,
            kind        TEXT NOT NULL CHECK (kind IN ('inline', 'offer')),
            source_kind TEXT NOT NULL,
            source_id   UUID NOT NULL,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS surfacing_memory_lookup_idx"
        " ON surfacing_memory (source_kind, source_id, kind, recorded_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS surfacing_memory")
