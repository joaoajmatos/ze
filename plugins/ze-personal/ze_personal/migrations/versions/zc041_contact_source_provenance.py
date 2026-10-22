"""Re-stamp contact provenance from where each contact came from.

Email, calendar, conversation and manual sources are the user's own material
(`prompt_supplied`); research is a web search (`live_search`). A contact takes
the provenance of its earliest source. Contacts without a source are untouched.

Revision ID: zc041
Revises: zc040
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from ze_logging import get_logger

revision: str = "zc041"
down_revision: Union[str, Sequence[str], None] = "zc040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REPAIR_SQL = """
WITH wanted AS (
    SELECT id, contact_id, created_at,
           CASE source_type
               WHEN 'research' THEN 'live_search'
               WHEN 'manual' THEN 'prompt_supplied'
               WHEN 'conversation' THEN 'prompt_supplied'
               WHEN 'email' THEN 'prompt_supplied'
               WHEN 'calendar' THEN 'prompt_supplied'
           END AS provenance
    FROM contact_sources
),
fixed_sources AS (
    UPDATE contact_sources cs
    SET provenance = w.provenance
    FROM wanted w
    WHERE cs.id = w.id AND cs.provenance <> w.provenance
    RETURNING cs.id
),
earliest AS (
    SELECT DISTINCT ON (contact_id) contact_id, provenance
    FROM wanted
    WHERE provenance IS NOT NULL
    ORDER BY contact_id, created_at, id
),
fixed_contacts AS (
    UPDATE contacts c
    SET provenance = e.provenance
    FROM earliest e
    WHERE c.id = e.contact_id AND c.provenance <> e.provenance
    RETURNING c.id
)
SELECT (SELECT count(*) FROM fixed_sources) AS sources,
       (SELECT count(*) FROM fixed_contacts) AS contacts
"""


def upgrade() -> None:
    row = op.get_bind().exec_driver_sql(REPAIR_SQL).one()
    get_logger(__name__).info(
        "zc041_restamped", sources=row.sources, contacts=row.contacts
    )


def downgrade() -> None:
    # Pre-v1 hard cut: the old labels were wrong, so there is nothing to restore.
    pass
