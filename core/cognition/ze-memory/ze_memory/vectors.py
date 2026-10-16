from __future__ import annotations

from typing import Any


def to_vector_literal(embedding: Any) -> str:
    """Render an embedding as a pgvector text literal for a ``$n::vector`` bind."""
    vals = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
    return "[" + ",".join(str(v) for v in vals) + "]"
