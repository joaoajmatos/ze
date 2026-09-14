"""Drop contact_relationships — retired in favor of COLLABORATES_WITH graph
edges in memory_relationships (Social Cognition Foundation).

Revision ID: zc029
Revises: zc028
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zc029"
down_revision: Union[str, Sequence[str], None] = "zc028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE contact_relationships")


def downgrade() -> None:
    op.execute("""
        CREATE TABLE contact_relationships (
            id                       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            person_a_id              UUID        NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            person_b_id              UUID        NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            relationship_description TEXT        NOT NULL,
            confidence               FLOAT       NOT NULL DEFAULT 0.5,
            source_type              TEXT        NOT NULL,
            claim_kind               TEXT        NOT NULL DEFAULT 'identity',
            provenance               TEXT        NOT NULL DEFAULT 'prompt_supplied',
            created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(person_a_id, person_b_id)
        )
    """)
    op.execute("""
        CREATE INDEX contact_relationships_a_idx
            ON contact_relationships (person_a_id)
    """)
    op.execute("""
        CREATE INDEX contact_relationships_b_idx
            ON contact_relationships (person_b_id)
    """)
