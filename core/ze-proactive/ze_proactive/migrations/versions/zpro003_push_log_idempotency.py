"""push_log idempotency key + unique index for at-most-one push per event.

Revision ID: zpro003
Revises: zpro002
Branch labels: ze_proactive
Depends on:
"""

from __future__ import annotations
from typing import Sequence, Union
from alembic import op

revision: str = "zpro003"
down_revision: Union[str, Sequence[str], None] = "zpro002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE push_log ADD COLUMN IF NOT EXISTS idempotency_key TEXT")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_push_log_event_idempotency
            ON push_log (event_type, idempotency_key)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_push_log_event_idempotency")
    op.execute("ALTER TABLE push_log DROP COLUMN IF EXISTS idempotency_key")
