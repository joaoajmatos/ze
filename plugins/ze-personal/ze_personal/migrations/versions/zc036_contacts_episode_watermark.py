"""Contacts consolidator watermark on memory_episodes; drop episodes.contacts_extracted.

The consolidator reads memory_episodes and tracks progress with a ze-personal-owned
keyset watermark instead of a flag column on the legacy episodes table (zc013).

Revision ID: zc036
Revises: zc035
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zc036"
down_revision: Union[str, Sequence[str], None] = "zc035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE contacts_episode_watermark (
            id              INT         PRIMARY KEY DEFAULT 1 CHECK (id = 1),
            last_created_at TIMESTAMPTZ NOT NULL,
            last_episode_id UUID        NOT NULL,
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("DROP INDEX IF EXISTS episodes_contacts_extracted_idx")
    op.execute("ALTER TABLE episodes DROP COLUMN IF EXISTS contacts_extracted")


def downgrade() -> None:
    op.execute("""
        ALTER TABLE episodes
            ADD COLUMN IF NOT EXISTS contacts_extracted BOOLEAN NOT NULL DEFAULT FALSE
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS episodes_contacts_extracted_idx
            ON episodes (contacts_extracted, created_at)
    """)
    op.execute("DROP TABLE contacts_episode_watermark")
