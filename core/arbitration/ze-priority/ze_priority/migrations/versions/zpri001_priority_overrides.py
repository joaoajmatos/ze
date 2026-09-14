"""Add priority_overrides table — user-directed priority override (Phase 127).

Revision ID: zpri001
Revises:
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zpri001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS priority_overrides (
            id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_kind                 TEXT NOT NULL,
            source_id                   UUID NOT NULL,
            anchor_source_kind          TEXT NOT NULL,
            anchor_source_id            UUID NOT NULL,
            relation                    TEXT NOT NULL,
            pinned                      BOOLEAN NOT NULL DEFAULT false,
            submitted_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
            superseded_at               TIMESTAMPTZ NULL,
            contribution_domain_id      UUID NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS priority_overrides_active_idx"
        " ON priority_overrides (source_kind, source_id)"
        " WHERE superseded_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS priority_overrides")
