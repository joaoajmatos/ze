"""Write confirmation: held writes for unattended runs; drop milestone intent (Phase 181).

Revision ID: zc033
Revises: zc032
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zc033"
down_revision: Union[str, Sequence[str], None] = "zc032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE goal_milestones
            DROP COLUMN IF EXISTS intent,
            ADD COLUMN approved_writes TEXT[] NOT NULL DEFAULT '{}'
    """)
    op.execute("""
        ALTER TABLE workflow_executions
            DROP CONSTRAINT IF EXISTS workflow_executions_status_check,
            ADD CONSTRAINT workflow_executions_status_check
            CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'held'))
    """)
    op.execute("""
        CREATE TABLE held_writes (
            request_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            owner_ref TEXT NOT NULL,
            items JSONB NOT NULL,
            payload JSONB NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ NOT NULL,
            decided_at TIMESTAMPTZ
        )
    """)
    op.execute("""
        CREATE INDEX held_writes_status_expires_idx
            ON held_writes (status, expires_at)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS held_writes")
    op.execute("""
        ALTER TABLE workflow_executions
            DROP CONSTRAINT IF EXISTS workflow_executions_status_check,
            ADD CONSTRAINT workflow_executions_status_check
            CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled'))
    """)
    op.execute("""
        ALTER TABLE goal_milestones
            DROP COLUMN IF EXISTS approved_writes,
            ADD COLUMN intent TEXT NOT NULL DEFAULT 'execute'
    """)
