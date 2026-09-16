"""Governed procedure lifecycle tables (Phase 138).

Revision ID: zm022
Revises: zm021
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zm022"
down_revision: Union[str, Sequence[str], None] = "zm021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE procedure_identities (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            canonical_name TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('active', 'retired')),
            active_version_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX procedure_identities_name_idx
            ON procedure_identities (lower(canonical_name))
        """
    )
    op.execute(
        """
        CREATE TABLE procedure_candidates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            proposed_identity_id UUID REFERENCES procedure_identities(id),
            source_kind TEXT NOT NULL,
            provenance TEXT NOT NULL,
            name TEXT NOT NULL,
            trigger TEXT NOT NULL,
            preconditions JSONB NOT NULL DEFAULT '[]'::jsonb,
            steps JSONB NOT NULL DEFAULT '[]'::jsonb,
            success_criteria JSONB NOT NULL DEFAULT '[]'::jsonb,
            limits JSONB NOT NULL DEFAULT '[]'::jsonb,
            evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            learning_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            workspace_run_approved BOOLEAN NOT NULL DEFAULT false,
            status TEXT NOT NULL CHECK (status IN (
                'pending', 'needs_review', 'approved', 'rejected', 'withdrawn'
            )),
            submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            resolved_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE TABLE procedure_admissions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID NOT NULL REFERENCES procedure_candidates(id),
            decision TEXT NOT NULL CHECK (decision IN (
                'approve', 'reject', 'needs_review', 'withdraw'
            )),
            reason TEXT NOT NULL,
            reviewer TEXT NOT NULL,
            review_evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            review_learning_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE procedure_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            procedure_id UUID NOT NULL REFERENCES procedure_identities(id),
            version_number INT NOT NULL,
            name TEXT NOT NULL,
            trigger TEXT NOT NULL,
            preconditions JSONB NOT NULL DEFAULT '[]'::jsonb,
            steps JSONB NOT NULL DEFAULT '[]'::jsonb,
            success_criteria JSONB NOT NULL DEFAULT '[]'::jsonb,
            limits JSONB NOT NULL DEFAULT '[]'::jsonb,
            provenance TEXT NOT NULL,
            evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            learning_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            status TEXT NOT NULL CHECK (status IN (
                'active', 'superseded', 'rolled_back', 'retired'
            )),
            supersedes_version_id UUID,
            superseded_by_version_id UUID,
            admission_id UUID REFERENCES procedure_admissions(id),
            embedding VECTOR(384),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            ended_at TIMESTAMPTZ,
            UNIQUE (procedure_id, version_number)
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX procedure_versions_one_active
            ON procedure_versions (procedure_id)
            WHERE status = 'active'
        """
    )
    op.execute(
        """
        ALTER TABLE procedure_identities
            ADD CONSTRAINT procedure_identities_active_version_fk
            FOREIGN KEY (active_version_id) REFERENCES procedure_versions(id)
        """
    )
    op.execute(
        """
        CREATE TABLE procedure_feedback (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            procedure_version_id UUID NOT NULL REFERENCES procedure_versions(id),
            action_record_id UUID NOT NULL,
            outcome TEXT NOT NULL CHECK (outcome IN (
                'succeeded', 'failed', 'partial', 'abandoned'
            )),
            summary TEXT NOT NULL,
            evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            learning_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE procedure_lifecycle_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            kind TEXT NOT NULL,
            reason TEXT NOT NULL,
            identity_id UUID,
            candidate_id UUID,
            version_id UUID,
            evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            learning_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE procedure_provisionals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            goal_id UUID NOT NULL,
            execution_id UUID,
            candidate JSONB NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('open', 'submitted', 'discarded')),
            resolution_reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        INSERT INTO procedure_candidates (
            id, source_kind, provenance, name, trigger, preconditions, steps,
            success_criteria, evidence_refs, learning_refs, status, submitted_at
        )
        SELECT
            id,
            'goal',
            'synthesized',
            name,
            trigger,
            preconditions,
            steps,
            success_criteria,
            '[]'::jsonb,
            source_refs,
            'needs_review',
            created_at
        FROM memory_procedures
        """
    )
    op.execute("DROP TABLE IF EXISTS memory_procedures CASCADE")


def downgrade() -> None:
    raise NotImplementedError("pre-v1 hard cut: procedure lifecycle is not reversible")
