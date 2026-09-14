"""Add sidecar_dispatched to workspace_runs (Phase 129).

Revision ID: zws003
Revises: zws002
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zws003"
down_revision: Union[str, Sequence[str], None] = "zws002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = "zws002"


def upgrade() -> None:
    # True once POST /run has actually been called for this row's id — lets
    # RunWatcher.reattach distinguish "never reached the sidecar, safe to
    # mark failed outright" from "reached the sidecar, must query GET
    # /runs/{id} before concluding anything" (Phase 129 data-model.md).
    op.execute(
        "ALTER TABLE workspace_runs"
        " ADD COLUMN IF NOT EXISTS sidecar_dispatched BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE workspace_runs DROP COLUMN IF EXISTS sidecar_dispatched")
