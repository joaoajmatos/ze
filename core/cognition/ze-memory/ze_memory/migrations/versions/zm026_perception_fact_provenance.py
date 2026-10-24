"""Re-stamp perception facts that were labeled synthesized (Phase 199).

Conversation, ingestion and inbound-message facts were stored ``synthesized``,
so dream decay and expiry treated what the user said as a dream guess. Only the
dream promoter sets ``dream_run_id``, so a synthesized fact without one is a
perception fact. Confidence, review and contradiction flags are left as they
are; the log line counts the rows already damaged by decay.

Revision ID: zm026
Revises: zm025
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from ze_logging import get_logger

revision: str = "zm026"
down_revision: Union[str, Sequence[str], None] = "zm025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = get_logger(__name__)

COUNT_SQL = """
    SELECT count(*) AS restamped,
           count(*) FILTER (
               WHERE contradicted AND confidence < 0.25 AND NOT corroborated
           ) AS decay_damaged
    FROM memory_facts
    WHERE provenance = 'synthesized' AND dream_run_id IS NULL
"""

REPAIR_SQL = """
    UPDATE memory_facts SET provenance = 'prompt_supplied', claim_kind = 'fact'
    WHERE provenance = 'synthesized' AND dream_run_id IS NULL
"""


def upgrade() -> None:
    bind = op.get_bind()
    counts = bind.exec_driver_sql(COUNT_SQL).one()
    log.info(
        "zm026_restamped",
        restamped=counts.restamped,
        decay_damaged=counts.decay_damaged,
    )
    op.execute(REPAIR_SQL)


def downgrade() -> None:
    # Pre-v1: the old synthesized label on perception facts was wrong.
    pass
