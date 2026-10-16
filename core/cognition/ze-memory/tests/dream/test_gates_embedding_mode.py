from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_memory.dream.gates import ScoringGates


def _pool(rows: list[dict]) -> MagicMock:
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows)
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


def _embedder() -> MagicMock:
    embedder = MagicMock()
    embedder.encode_passage = MagicMock(return_value=[1.0, 0.0])
    embedder.encode_query = MagicMock(return_value=[1.0, 0.0])
    return embedder


async def test_novelty_gate_compares_stored_facts_as_passages():
    embedder = _embedder()
    gates = ScoringGates(_pool([{"embedding": [1.0, 0.0]}]), embedder)

    await gates.gate2_novelty("a synthesized pattern")

    embedder.encode_passage.assert_called_once_with("a synthesized pattern")
    embedder.encode_query.assert_not_called()


async def test_retrievability_gate_uses_the_content_as_a_query():
    embedder = _embedder()
    episode_id = uuid4()
    gates = ScoringGates(_pool([{"id": episode_id, "embedding": [1.0, 0.0]}]), embedder)

    await gates.gate3_retrievability("a synthesized pattern", [episode_id])

    embedder.encode_query.assert_called_once_with("a synthesized pattern")
    embedder.encode_passage.assert_not_called()
