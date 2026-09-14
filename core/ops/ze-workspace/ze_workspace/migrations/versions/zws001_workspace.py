"""Add workspace_state and workspace_runs tables (Phase 115).

Revision ID: zws001
Revises:
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zws001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_state (
            id              SMALLINT PRIMARY KEY CHECK (id = 1),
            mode            TEXT NOT NULL DEFAULT 'ask',
            last_reset_at   TIMESTAMPTZ NULL,
            last_used_at    TIMESTAMPTZ NULL,
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        INSERT INTO workspace_state (id, mode)
        VALUES (1, 'ask')
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_runs (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            ended_at            TIMESTAMPTZ NULL,
            command             TEXT NOT NULL,
            origin              TEXT NOT NULL,
            thread_id           TEXT NULL,
            message_id          UUID NULL,
            skill_id            UUID NULL,
            skill_script_path   TEXT NULL,
            status              TEXT NOT NULL,
            exit_code           INT NULL,
            output_preview      TEXT NOT NULL DEFAULT '',
            output_file_path    TEXT NULL,
            files_touched       JSONB NOT NULL DEFAULT '[]'::jsonb,
            error_summary       TEXT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS workspace_runs_started_idx"
        " ON workspace_runs (started_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS workspace_runs_thread_idx"
        " ON workspace_runs (thread_id, started_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS workspace_runs")
    op.execute("DROP TABLE IF EXISTS workspace_state")
