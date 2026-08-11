"""Rekey pending_confirmations from thread_id to request_id.

Revision ID: zc027
Revises: zc026
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zc027"
down_revision: Union[str, Sequence[str], None] = "zc026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE pending_confirmations DROP CONSTRAINT pending_confirmations_pkey")
    op.execute("ALTER TABLE pending_confirmations ADD PRIMARY KEY (request_id)")
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_pending_confirmations_thread_id
            ON pending_confirmations (thread_id)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_pending_confirmations_thread_id")
    op.execute("ALTER TABLE pending_confirmations DROP CONSTRAINT pending_confirmations_pkey")
    op.execute("ALTER TABLE pending_confirmations ADD PRIMARY KEY (thread_id)")
