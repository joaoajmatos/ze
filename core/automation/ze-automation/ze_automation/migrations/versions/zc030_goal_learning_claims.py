"""Authoritative evidence-backed goal learning tables.

Revision ID: zc030
Revises: zc029
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zc030"
down_revision: Union[str, Sequence[str], None] = "zc029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE goal_learning_claims (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
            content TEXT NOT NULL CHECK (char_length(btrim(content)) > 0),
            claim_kind TEXT NOT NULL,
            provenance TEXT NOT NULL,
            confidence DOUBLE PRECISION NOT NULL
                CHECK (confidence >= 0 AND confidence <= 1),
            status TEXT NOT NULL CHECK (status IN (
                'pending_review', 'active', 'review_needed', 'retracted', 'superseded'
            )),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            activated_at TIMESTAMPTZ,
            retracted_at TIMESTAMPTZ,
            superseded_by_id UUID REFERENCES goal_learning_claims(id),
            CONSTRAINT goal_learning_retracted_at_chk
                CHECK (status <> 'retracted' OR retracted_at IS NOT NULL),
            CONSTRAINT goal_learning_superseded_by_chk
                CHECK (status <> 'superseded' OR superseded_by_id IS NOT NULL)
        )
    """)
    op.execute("""
        CREATE INDEX goal_learning_claims_goal_status_idx
            ON goal_learning_claims (goal_id, status, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX goal_learning_claims_active_idx
            ON goal_learning_claims (status, claim_kind, confidence)
    """)
    op.execute("""
        CREATE TABLE goal_learning_evidence (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            learning_id UUID NOT NULL REFERENCES goal_learning_claims(id) ON DELETE CASCADE,
            evidence_kind TEXT NOT NULL CHECK (evidence_kind IN (
                'action_record', 'user_confirmation', 'user_correction'
            )),
            action_record_id UUID,
            review_id UUID,
            role TEXT NOT NULL CHECK (role IN ('supports', 'contradicts', 'derives')),
            execution_context_key TEXT,
            excerpt TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT goal_learning_evidence_source_chk CHECK (
                (action_record_id IS NOT NULL AND review_id IS NULL)
                OR (action_record_id IS NULL AND review_id IS NOT NULL)
            )
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX goal_learning_evidence_action_uniq
            ON goal_learning_evidence (
                learning_id, evidence_kind, action_record_id, role
            )
            WHERE action_record_id IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX goal_learning_evidence_learning_role_idx
            ON goal_learning_evidence (learning_id, role)
    """)
    op.execute("""
        CREATE INDEX goal_learning_evidence_action_idx
            ON goal_learning_evidence (action_record_id)
    """)
    op.execute("""
        CREATE INDEX goal_learning_evidence_context_idx
            ON goal_learning_evidence (execution_context_key)
    """)
    op.execute("""
        CREATE TABLE goal_learning_reviews (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            learning_id UUID NOT NULL REFERENCES goal_learning_claims(id) ON DELETE CASCADE,
            decision TEXT NOT NULL CHECK (decision IN (
                'approve', 'reject', 'correct', 'defer', 'retain'
            )),
            actor_kind TEXT NOT NULL CHECK (actor_kind IN ('user', 'system')),
            rationale TEXT,
            corrected_content TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        ALTER TABLE goal_learning_evidence
            ADD CONSTRAINT goal_learning_evidence_review_fk
            FOREIGN KEY (review_id) REFERENCES goal_learning_reviews(id)
    """)
    op.execute("""
        CREATE TABLE goal_learning_relationships (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            from_learning_id UUID NOT NULL REFERENCES goal_learning_claims(id) ON DELETE CASCADE,
            to_learning_id UUID NOT NULL REFERENCES goal_learning_claims(id) ON DELETE CASCADE,
            relationship TEXT NOT NULL CHECK (relationship IN (
                'corroborates', 'contradicts', 'supersedes'
            )),
            basis TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE goal_learning_promotions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            learning_id UUID NOT NULL REFERENCES goal_learning_claims(id) ON DELETE CASCADE,
            state TEXT NOT NULL CHECK (state IN (
                'pending', 'promoted', 'failed', 'blocked'
            )),
            memory_fact_id UUID,
            eligibility_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
            failure_reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX goal_learning_promotions_active_uniq
            ON goal_learning_promotions (learning_id)
            WHERE state IN ('pending', 'promoted')
    """)
    op.execute("""
        INSERT INTO goal_learning_claims (
            id, goal_id, content, claim_kind, provenance, confidence, status, created_at, updated_at
        )
        SELECT
            id,
            goal_id,
            content,
            'inference',
            'synthesized',
            0.4,
            'review_needed',
            COALESCE(created_at, NOW()),
            COALESCE(created_at, NOW())
        FROM goal_learnings
        WHERE char_length(btrim(content)) > 0
    """)
    op.execute("""
        INSERT INTO goal_learning_claims (
            goal_id, content, claim_kind, provenance, confidence, status
        )
        SELECT g.id, btrim(line), 'inference', 'synthesized', 0.3, 'review_needed'
        FROM goals g
        CROSS JOIN LATERAL unnest(string_to_array(g.learnings, E'\\n')) AS line
        WHERE g.learnings IS NOT NULL
          AND g.learnings <> ''
          AND char_length(btrim(line)) > 0
          AND NOT EXISTS (
              SELECT 1 FROM goal_learning_claims c
              WHERE c.goal_id = g.id AND c.content = btrim(line)
          )
    """)
    op.execute("ALTER TABLE goals DROP COLUMN IF EXISTS learnings")
    op.execute("DROP TABLE IF EXISTS goal_learnings")


def downgrade() -> None:
    raise NotImplementedError("pre-v1 hard cut: goal learning schema is not reversible")
