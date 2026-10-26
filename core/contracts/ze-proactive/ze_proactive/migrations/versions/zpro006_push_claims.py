"""push_log becomes the governor's claim table: claim_key + discretionary flag.

Revision ID: zpro006
Revises: zpro005
Branch labels: ze_proactive
Depends on:
"""

from __future__ import annotations
from typing import Sequence, Union
from alembic import op

revision: str = "zpro006"
down_revision: Union[str, Sequence[str], None] = "zpro005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DELETE_NON_CLAIMS_SQL = (
    "DELETE FROM push_log WHERE event_type <> 'attention_push' "
    "OR idempotency_key IS NULL"
)


def upgrade() -> None:
    op.execute(DELETE_NON_CLAIMS_SQL)
    op.execute("DROP INDEX IF EXISTS ux_push_log_event_idempotency")
    op.execute("DROP INDEX IF EXISTS push_log_event_type_sent_at_idx")
    op.execute("ALTER TABLE push_log RENAME COLUMN idempotency_key TO claim_key")
    op.execute("ALTER TABLE push_log ALTER COLUMN claim_key SET NOT NULL")
    op.execute(
        "ALTER TABLE push_log ADD COLUMN discretionary BOOLEAN NOT NULL DEFAULT TRUE"
    )
    op.execute("ALTER TABLE push_log ALTER COLUMN discretionary DROP DEFAULT")
    op.execute(
        "CREATE INDEX push_log_claim_key_sent_at_idx "
        "ON push_log (claim_key, sent_at DESC)"
    )
    op.execute(
        "CREATE INDEX push_log_discretionary_sent_at_idx "
        "ON push_log (sent_at) WHERE discretionary"
    )


def downgrade() -> None:
    """Older repeat claims of one key are dropped (the newest stays), because the
    old schema's unique index allows one row per (event_type, key)."""
    op.execute(
        "DELETE FROM push_log a USING push_log b "
        "WHERE a.event_type = b.event_type AND a.claim_key = b.claim_key "
        "AND a.id < b.id"
    )
    op.execute("DROP INDEX IF EXISTS push_log_discretionary_sent_at_idx")
    op.execute("DROP INDEX IF EXISTS push_log_claim_key_sent_at_idx")
    op.execute("ALTER TABLE push_log DROP COLUMN IF EXISTS discretionary")
    op.execute("ALTER TABLE push_log ALTER COLUMN claim_key DROP NOT NULL")
    op.execute("ALTER TABLE push_log RENAME COLUMN claim_key TO idempotency_key")
    op.execute(
        "CREATE INDEX IF NOT EXISTS push_log_event_type_sent_at_idx "
        "ON push_log (event_type, sent_at DESC)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_push_log_event_idempotency "
        "ON push_log (event_type, idempotency_key)"
    )
