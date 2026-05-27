"""Add contact_channels table

Revision ID: 015
Revises: 014
Create Date: 2026-05-25
"""
from typing import Sequence, Union

from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS contact_channels (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            contact_id   UUID        NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            channel_type TEXT        NOT NULL,
            handle       TEXT        NOT NULL,
            preferred    BOOLEAN     NOT NULL DEFAULT FALSE,
            verified     BOOLEAN     NOT NULL DEFAULT FALSE,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(contact_id, channel_type, handle)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS contact_channels_contact_id_idx
            ON contact_channels(contact_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS contact_channels_type_idx
            ON contact_channels(channel_type)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS contact_channels")
