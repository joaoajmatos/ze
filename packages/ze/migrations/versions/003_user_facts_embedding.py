"""Add embedding column to user_facts for semantic retrieval

Revision ID: 003
Revises: 002
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL for existing rows — _load_facts falls back to recency for these.
    op.execute("ALTER TABLE user_facts ADD COLUMN IF NOT EXISTS embedding VECTOR(384)")
    op.execute("""
        CREATE INDEX IF NOT EXISTS user_facts_embedding_idx
        ON user_facts USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS user_facts_embedding_idx")
    op.execute("ALTER TABLE user_facts DROP COLUMN IF EXISTS embedding")
