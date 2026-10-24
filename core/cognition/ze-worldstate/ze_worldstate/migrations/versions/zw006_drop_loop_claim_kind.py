"""Drop open_loops.claim_kind (Phase 199).

A loop's claim kind is derived from its state, so the stored column could only
go stale (a confirmed loop kept `suspicion`).

Revision ID: zw006
Revises: zw005
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zw006"
down_revision: Union[str, Sequence[str], None] = "zw005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE open_loops DROP COLUMN IF EXISTS claim_kind")


def downgrade() -> None:
    # The old column was NOT NULL; a dropped loop has no kind now, so the restore
    # maps it to suspicion.
    op.execute("ALTER TABLE open_loops ADD COLUMN IF NOT EXISTS claim_kind TEXT")
    op.execute(
        "UPDATE open_loops SET claim_kind = CASE state "
        "WHEN 'suspected' THEN 'suspicion' "
        "WHEN 'dropped' THEN 'suspicion' "
        "ELSE 'priority' END"
    )
    op.execute("ALTER TABLE open_loops ALTER COLUMN claim_kind SET NOT NULL")
