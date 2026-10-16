"""Memory-context → ``MemoryChunkTrace`` rows, shared by the trace, the turn and the tier state."""

from __future__ import annotations

from typing import Any

from ze_core.conversation.messages.types import MemoryChunkTrace

_MAX_MEMORY_CHUNKS = 10


def extract_memory_chunks(memory_context: Any) -> list[MemoryChunkTrace]:
    if memory_context is None:
        return []

    chunks: list[MemoryChunkTrace] = []

    facts = getattr(memory_context, "facts", []) or []
    for fact in facts[:5]:
        text = f"{fact.predicate}: {fact.value}"
        chunks.append(
            MemoryChunkTrace(
                text=text[:300],
                score=getattr(fact, "relevance_score", None) or 0.0,
                source="fact",
                extraction_confidence=getattr(fact, "confidence", None),
            )
        )

    episodes = getattr(memory_context, "episodes", []) or []
    for ep in episodes[:5]:
        text = getattr(ep, "summary", None) or (
            ep.response[:300] if hasattr(ep, "response") else ""
        )
        chunks.append(
            MemoryChunkTrace(
                text=text[:300],
                score=getattr(ep, "relevance_score", None) or 0.0,
                source="episode",
            )
        )

    return chunks[:_MAX_MEMORY_CHUNKS]
