"""Narrow goal_learning_evidence CHECKs to the values the code writes.

No producer writes evidence_kind 'user_correction' or role 'derives'; their enum
members are gone from ze_automation.goals.types.

Revision ID: zc037
Revises: zc036
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zc037"
down_revision: Union[str, Sequence[str], None] = "zc036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE goal_learning_evidence
            DROP CONSTRAINT goal_learning_evidence_evidence_kind_check,
            ADD CONSTRAINT goal_learning_evidence_evidence_kind_check
                CHECK (evidence_kind IN ('action_record', 'user_confirmation')),
            DROP CONSTRAINT goal_learning_evidence_role_check,
            ADD CONSTRAINT goal_learning_evidence_role_check
                CHECK (role IN ('supports', 'contradicts'))
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE goal_learning_evidence
            DROP CONSTRAINT goal_learning_evidence_evidence_kind_check,
            ADD CONSTRAINT goal_learning_evidence_evidence_kind_check
                CHECK (evidence_kind IN (
                    'action_record', 'user_confirmation', 'user_correction'
                )),
            DROP CONSTRAINT goal_learning_evidence_role_check,
            ADD CONSTRAINT goal_learning_evidence_role_check
                CHECK (role IN ('supports', 'contradicts', 'derives'))
    """)
