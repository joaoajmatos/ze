"""interruption governor: notification classes, quiet-hours settings, job runs.

Revision ID: zpro004
Revises: zpro003
Branch labels: ze_proactive
Depends on:
"""

from __future__ import annotations
from typing import Sequence, Union
from alembic import op

revision: str = "zpro004"
down_revision: Union[str, Sequence[str], None] = "zpro003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE notifications
            ADD COLUMN IF NOT EXISTS push_class   TEXT,
            ADD COLUMN IF NOT EXISTS urgency      TEXT,
            ADD COLUMN IF NOT EXISTS format       TEXT NOT NULL DEFAULT 'text',
            ADD COLUMN IF NOT EXISTS actions      JSONB NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS delivery     TEXT,
            ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ
    """)
    op.execute("""
        UPDATE notifications
        SET push_class   = COALESCE(push_class, 'accountability'),
            urgency      = COALESCE(urgency, 'normal'),
            delivery     = COALESCE(delivery, 'delivered'),
            delivered_at = COALESCE(delivered_at, created_at)
    """)
    op.execute("""
        ALTER TABLE notifications
            ALTER COLUMN push_class SET NOT NULL,
            ALTER COLUMN urgency    SET NOT NULL,
            ALTER COLUMN delivery   SET NOT NULL
    """)
    op.execute("""
        ALTER TABLE notifications
            ADD CONSTRAINT notifications_push_class_check
                CHECK (push_class IN ('requested', 'accountability', 'discretionary')),
            ADD CONSTRAINT notifications_urgency_check
                CHECK (urgency IN ('low', 'normal', 'high')),
            ADD CONSTRAINT notifications_format_check
                CHECK (format IN ('text', 'markdown', 'html')),
            ADD CONSTRAINT notifications_delivery_check
                CHECK (delivery IN ('delivered', 'held', 'released', 'suppressed', 'failed'))
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS notifications_held_idx
            ON notifications (created_at) WHERE delivery = 'held'
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS interruption_settings (
            id                  BOOLEAN     PRIMARY KEY DEFAULT TRUE CHECK (id),
            quiet_hours_enabled BOOLEAN     NOT NULL DEFAULT FALSE,
            quiet_start         TIME,
            quiet_end           TIME,
            timezone            TEXT,
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CHECK (
                NOT quiet_hours_enabled
                OR (quiet_start IS NOT NULL AND quiet_end IS NOT NULL
                    AND timezone IS NOT NULL AND quiet_start <> quiet_end)
            )
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS proactive_job_runs (
            job_id           TEXT        PRIMARY KEY,
            last_started_at  TIMESTAMPTZ NOT NULL,
            last_finished_at TIMESTAMPTZ,
            last_status      TEXT        NOT NULL
                CHECK (last_status IN ('running', 'ok', 'error'))
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS proactive_job_runs")
    op.execute("DROP TABLE IF EXISTS interruption_settings")
    op.execute("DROP INDEX IF EXISTS notifications_held_idx")
    op.execute("""
        ALTER TABLE notifications
            DROP CONSTRAINT IF EXISTS notifications_push_class_check,
            DROP CONSTRAINT IF EXISTS notifications_urgency_check,
            DROP CONSTRAINT IF EXISTS notifications_format_check,
            DROP CONSTRAINT IF EXISTS notifications_delivery_check
    """)
    op.execute("""
        ALTER TABLE notifications
            DROP COLUMN IF EXISTS delivered_at,
            DROP COLUMN IF EXISTS delivery,
            DROP COLUMN IF EXISTS actions,
            DROP COLUMN IF EXISTS format,
            DROP COLUMN IF EXISTS urgency,
            DROP COLUMN IF EXISTS push_class
    """)
