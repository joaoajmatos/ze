"""Add contribution_collisions table (Phase 126).

Revision ID: zcol001
Revises:
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zcol001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS contribution_collisions (
            id                                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            contribution_a_domain_id           UUID NOT NULL,
            contribution_a_producer_kind       TEXT NOT NULL,
            contribution_a_source_function     TEXT NOT NULL,
            contribution_a_claim_kind          TEXT NOT NULL,
            contribution_b_domain_id           UUID NOT NULL,
            contribution_b_producer_kind       TEXT NOT NULL,
            contribution_b_source_function     TEXT NOT NULL,
            contribution_b_claim_kind          TEXT NOT NULL,
            matched_entity_id                  UUID NULL,
            matched_target_face                TEXT NOT NULL,
            conflict_summary                   TEXT NOT NULL,
            created_at                         TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS contribution_collisions_entity_idx"
        " ON contribution_collisions (matched_entity_id, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS contribution_collisions_functions_idx"
        " ON contribution_collisions"
        " (contribution_a_source_function, contribution_b_source_function, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS contribution_collisions_created_at_idx"
        " ON contribution_collisions (created_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS contribution_collisions")
