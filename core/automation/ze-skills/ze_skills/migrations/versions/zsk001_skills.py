"""Add skills, skill_reference_files, skill_reviews tables (Phase 114).

Revision ID: zsk001
Revises:
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zsk001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS skills (
            id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name                     TEXT NOT NULL,
            slug                     TEXT NOT NULL,
            description              TEXT NOT NULL,
            instructions             TEXT NOT NULL,
            source                   TEXT NOT NULL,
            origin_url               TEXT NULL,
            bundling_plugin          TEXT NULL,
            status                   TEXT NOT NULL DEFAULT 'pending_review',
            allowed_tools            JSONB NULL,
            has_unsupported_scripts  BOOLEAN NOT NULL DEFAULT false,
            content_hash             TEXT NOT NULL,
            created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
            approved_at              TIMESTAMPTZ NULL,
            last_checked_at          TIMESTAMPTZ NULL,
            last_check_error         TEXT NULL
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS skills_slug_source_idx"
        " ON skills (slug, source)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS skills_status_idx ON skills (status)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS skill_reference_files (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            skill_id      UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
            filename      TEXT NOT NULL,
            content       TEXT NOT NULL,
            content_type  TEXT NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS skill_reference_files_skill_idx"
        " ON skill_reference_files (skill_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS skill_reviews (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            skill_id          UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
            content_snapshot  JSONB NOT NULL,
            decision          TEXT NOT NULL,
            decided_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS skill_reviews_skill_idx ON skill_reviews (skill_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS skill_reviews")
    op.execute("DROP TABLE IF EXISTS skill_reference_files")
    op.execute("DROP TABLE IF EXISTS skills")
