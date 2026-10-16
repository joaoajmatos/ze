"""Drop the legacy memory tables user_facts, episodes and user_profile (zc001).

ze-memory owns memory since phase 2's rewrite (memory_facts, memory_episodes,
memory_profile_facets). Nothing writes these tables; the last reader, the contacts
consolidator, moved to memory_episodes in zc036.

Revision ID: zc037
Revises: zc036
Depends on: zc022
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zc037"
down_revision: Union[str, Sequence[str], None] = "zc036"
branch_labels: Union[str, Sequence[str], None] = None
# zc022 resizes these tables on the zc020 -> zc024 branch, which does not
# precede zc036 in the chain.
depends_on: Union[str, Sequence[str], None] = "zc022"


def upgrade() -> None:
    op.execute("DROP TABLE user_facts")
    op.execute("DROP TABLE episodes")
    op.execute("DROP TABLE user_profile")


def downgrade() -> None:
    op.execute("""
        CREATE TABLE user_facts (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            key          TEXT        NOT NULL,
            value        TEXT        NOT NULL,
            agent        TEXT        NOT NULL DEFAULT 'global',
            confidence   FLOAT       NOT NULL DEFAULT 1.0,
            reviewed     BOOLEAN     NOT NULL DEFAULT false,
            contradicted BOOLEAN     NOT NULL DEFAULT false,
            embedding    VECTOR(768),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at   TIMESTAMPTZ
        )
    """)
    op.execute("""
        CREATE INDEX user_facts_retrieval_idx
            ON user_facts (contradicted, agent, updated_at DESC)
    """)
    op.execute("""
        CREATE INDEX user_facts_embedding_idx
            ON user_facts USING hnsw (embedding vector_cosine_ops)
            WHERE embedding IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX user_facts_expires_at_idx
            ON user_facts (expires_at) WHERE expires_at IS NOT NULL
    """)
    op.execute("""
        CREATE TABLE episodes (
            id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            agent      TEXT        NOT NULL,
            prompt     TEXT        NOT NULL,
            response   TEXT        NOT NULL,
            summary    TEXT,
            embedding  VECTOR(768),
            is_archive BOOLEAN     NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX episodes_created_idx ON episodes (created_at DESC)")
    op.execute("""
        CREATE INDEX episodes_embedding_idx
            ON episodes USING hnsw (embedding vector_cosine_ops)
            WHERE embedding IS NOT NULL
    """)
    op.execute("""
        CREATE TABLE user_profile (
            id            INT         PRIMARY KEY DEFAULT 1,
            preferences   TEXT        NOT NULL DEFAULT '',
            habits        TEXT        NOT NULL DEFAULT '',
            topics        TEXT        NOT NULL DEFAULT '',
            relationships TEXT        NOT NULL DEFAULT '',
            goals         TEXT        NOT NULL DEFAULT '',
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            version       INT         NOT NULL DEFAULT 0
        )
    """)
