"""Resize embedding columns from VECTOR(384) to VECTOR(768) for E5-base model.

Embeddings in memory tables were computed with paraphrase-multilingual-MiniLM-L12-v2
(384-dim). The new E5-base model produces 768-dim vectors. Columns must be resized
and HNSW indexes rebuilt. Existing embeddings are NULLed — they will be recomputed
on next write.

news_articles embeddings are excluded — the fetch job re-embeds all articles within
30 minutes of deployment, and the table has no HNSW index to rebuild.

Revision ID: zm013
Revises: zm012
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "zm013"
down_revision: Union[str, Sequence[str], None] = "zm012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXED_TABLES = [
    ("memory_entities", "memory_entities_embedding_idx"),
    ("memory_facts", "memory_facts_embedding_idx"),
    ("memory_episodes", "memory_episodes_embedding_idx"),
    ("memory_procedures", "memory_procedures_embedding_idx"),
    ("memory_session_summaries", "memory_session_summaries_embedding_idx"),
]

_UNINDEXED_TABLES = ["memory_events"]


def upgrade() -> None:
    # NULL first so the column type change doesn't choke on existing 384-dim data
    for table, _ in _INDEXED_TABLES:
        op.execute(f"UPDATE {table} SET embedding = NULL WHERE embedding IS NOT NULL")
    for table in _UNINDEXED_TABLES:
        op.execute(f"UPDATE {table} SET embedding = NULL WHERE embedding IS NOT NULL")

    # Drop HNSW indexes before altering column type (pgvector requirement)
    for _, idx in _INDEXED_TABLES:
        op.execute(f"DROP INDEX IF EXISTS {idx}")

    # Resize all embedding columns to 768-dim
    for table, _ in _INDEXED_TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE VECTOR(768)")
    for table in _UNINDEXED_TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE VECTOR(768)")

    # news_articles belongs to the ze-news chain, which may run after this one.
    # zn001 creates the column at 768 dims; this covers databases that already
    # had the 384-dim table. IF EXISTS keeps a fresh database from failing here.
    op.execute(
        "ALTER TABLE IF EXISTS news_articles "
        "ALTER COLUMN embedding TYPE VECTOR(768) USING NULL"
    )

    # Recreate HNSW indexes for new dimension
    for table, idx in _INDEXED_TABLES:
        op.execute(f"""
            CREATE INDEX IF NOT EXISTS {idx}
            ON {table} USING hnsw (embedding vector_cosine_ops)
            WHERE embedding IS NOT NULL
        """)


def downgrade() -> None:
    # Embeddings cannot be restored to 384-dim — downgrade is a no-op.
    pass
