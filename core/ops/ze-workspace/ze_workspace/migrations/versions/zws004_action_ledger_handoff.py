"""Ledger handoff columns on workspace_runs (Phase 135).

Revision ID: zws004
Revises: zws003
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zws004"
down_revision: Union[str, Sequence[str], None] = "zws003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = "zws003"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE workspace_runs"
        " ADD COLUMN IF NOT EXISTS ledger_idempotency_key TEXT"
    )
    op.execute(
        "ALTER TABLE workspace_runs"
        " ADD COLUMN IF NOT EXISTS ledger_pending BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE workspace_runs DROP COLUMN IF EXISTS ledger_pending")
    op.execute(
        "ALTER TABLE workspace_runs DROP COLUMN IF EXISTS ledger_idempotency_key"
    )
