"""Unwrap string-shaped action_records JSON and index the subject keys (Phase 194).

Before this revision the store sent json.dumps text through a pool whose jsonb codec
dumps again, so context, evidence and causal_refs were stored as JSON strings and
``context->>'goal_id'`` matched nothing.

Revision ID: zm025
Revises: zm024
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zm025"
down_revision: Union[str, Sequence[str], None] = "zm024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SUBJECT_KEYS = ("goal_id", "workflow_id", "workflow_run_id", "workspace_run_id")

REPAIR_SQL = """
    UPDATE action_records SET
        context = CASE WHEN jsonb_typeof(context) = 'string'
                       THEN (context #>> '{}')::jsonb ELSE context END,
        evidence = CASE WHEN jsonb_typeof(evidence) = 'string'
                        THEN (evidence #>> '{}')::jsonb ELSE evidence END,
        causal_refs = CASE WHEN jsonb_typeof(causal_refs) = 'string'
                           THEN (causal_refs #>> '{}')::jsonb ELSE causal_refs END
    WHERE jsonb_typeof(context) = 'string'
       OR jsonb_typeof(evidence) = 'string'
       OR jsonb_typeof(causal_refs) = 'string'
"""


def upgrade() -> None:
    op.execute(REPAIR_SQL)
    for key in SUBJECT_KEYS:
        op.execute(
            f"""
            CREATE INDEX IF NOT EXISTS action_records_{key}_idx
                ON action_records ((context->>'{key}'), occurred_at DESC, id DESC)
                WHERE context->>'{key}' IS NOT NULL
            """
        )


def downgrade() -> None:
    for key in SUBJECT_KEYS:
        op.execute(f"DROP INDEX IF EXISTS action_records_{key}_idx")
