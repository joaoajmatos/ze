"""Procedure activation ledger (Phase 139).

Revision ID: zm023
Revises: zm022
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zm023"
down_revision: Union[str, Sequence[str], None] = "zm022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE procedure_invocations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            procedure_id UUID NOT NULL,
            version_id UUID NOT NULL,
            origin TEXT NOT NULL,
            caller TEXT NOT NULL,
            task_context_ref TEXT,
            state TEXT NOT NULL CHECK (state IN (
                'started', 'completed', 'failed', 'cancelled'
            )),
            outcome_id UUID,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE TABLE procedure_action_links (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            invocation_id UUID NOT NULL REFERENCES procedure_invocations(id),
            procedure_id UUID NOT NULL,
            version_id UUID NOT NULL,
            step_ref TEXT NOT NULL,
            action_trace_ref TEXT,
            capability_decision TEXT NOT NULL,
            outcome TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE procedure_activation_feedback (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            invocation_id UUID NOT NULL UNIQUE REFERENCES procedure_invocations(id),
            procedure_id UUID NOT NULL,
            version_id UUID NOT NULL,
            outcome TEXT NOT NULL,
            summary TEXT NOT NULL,
            action_link_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    raise NotImplementedError("pre-v1 hard cut: procedure activation is not reversible")
