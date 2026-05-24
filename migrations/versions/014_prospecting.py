"""Add prospect_campaigns and prospect_outreach tables

Revision ID: 014
Revises: 013
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS prospect_campaigns (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            brief        TEXT        NOT NULL,
            status       TEXT        NOT NULL DEFAULT 'running',
            target_count INT,
            found_count  INT         NOT NULL DEFAULT 0,
            output       TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS prospect_campaigns_status_idx
            ON prospect_campaigns(status, created_at DESC)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS prospect_outreach (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            campaign_id UUID        REFERENCES prospect_campaigns(id) ON DELETE CASCADE,
            contact_id  UUID        NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            channel     TEXT        NOT NULL,
            status      TEXT        NOT NULL DEFAULT 'pending',
            draft       TEXT,
            sent_at     TIMESTAMPTZ,
            replied_at  TIMESTAMPTZ,
            notes       TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(campaign_id, contact_id)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS prospect_outreach_campaign_idx
            ON prospect_outreach(campaign_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS prospect_outreach_contact_idx
            ON prospect_outreach(contact_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS prospect_outreach_status_idx
            ON prospect_outreach(status, created_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS prospect_outreach")
    op.execute("DROP TABLE IF EXISTS prospect_campaigns")
