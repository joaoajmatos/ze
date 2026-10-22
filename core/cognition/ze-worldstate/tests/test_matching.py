from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

from ze_worldstate.matching import find_matching_loop
from ze_worldstate.types import LoopProvenance, LoopState, OpenLoop


def _loop(**overrides) -> OpenLoop:
    base = dict(
        id=uuid4(),
        title="Renew passport",
        provenance=LoopProvenance.CONVERSATION,
        confidence=0.3,
        state=LoopState.SUSPECTED,
    )
    base.update(overrides)
    return OpenLoop(**base)


def _rel(target_id, target_type="open_loop"):
    from ze_memory.graph.types import Relationship

    return Relationship(
        source_id=uuid4(),
        source_type="entity",
        predicate="has_open_loop",
        target_id=target_id,
        target_type=target_type,
    )


async def test_single_entity_match_returns_that_loop():
    existing = _loop()
    graph_store = AsyncMock()
    graph_store.list_relationships = AsyncMock(return_value=[_rel(existing.id)])
    loop_store = AsyncMock()
    loop_store.get = AsyncMock(return_value=existing)
    embedder = AsyncMock()

    result = await find_matching_loop(
        [uuid4()],
        "Renew passport before trip",
        loop_store=loop_store,
        graph_store=graph_store,
        embedder=embedder,
    )
    assert result is existing


async def test_zero_entity_matches_falls_back_to_embedding_similarity():
    existing = _loop(title="renew passport")
    graph_store = AsyncMock()
    graph_store.list_relationships = AsyncMock(return_value=[])
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[existing])

    embedder = AsyncMock()
    embedder.encode_passage = embedder.encode_query = lambda text: (
        [1.0, 0.0] if "passport" in text.lower() else [0.0, 1.0]
    )

    result = await find_matching_loop(
        [],
        "renew passport",
        loop_store=loop_store,
        graph_store=graph_store,
        embedder=embedder,
    )
    assert result is existing


async def test_no_similarity_match_returns_none():
    existing = _loop(title="buy groceries")
    graph_store = AsyncMock()
    graph_store.list_relationships = AsyncMock(return_value=[])
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[existing])

    embedder = AsyncMock()
    embedder.encode_passage = embedder.encode_query = lambda text: (
        [1.0, 0.0] if "passport" in text.lower() else [0.0, 1.0]
    )

    result = await find_matching_loop(
        [],
        "renew passport",
        loop_store=loop_store,
        graph_store=graph_store,
        embedder=embedder,
    )
    assert result is None


async def test_dismissed_state_filter_only_considers_dropped_loops():
    dropped = _loop(state=LoopState.DROPPED)
    graph_store = AsyncMock()
    graph_store.list_relationships = AsyncMock(return_value=[_rel(dropped.id)])
    loop_store = AsyncMock()
    loop_store.get = AsyncMock(return_value=dropped)
    embedder = AsyncMock()

    result = await find_matching_loop(
        [uuid4()],
        "renew passport",
        loop_store=loop_store,
        graph_store=graph_store,
        embedder=embedder,
        states=["dropped"],
    )
    assert result is dropped


def _passport_embedder():
    embedder = AsyncMock()
    embedder.encode_passage = embedder.encode_query = lambda text: (
        [1.0, 0.0] if "passport" in text.lower() else [0.0, 1.0]
    )
    return embedder


async def _lone_candidate(title, candidate_title, **kw):
    existing = _loop(title=title)
    graph_store = AsyncMock()
    graph_store.list_relationships = AsyncMock(return_value=[_rel(existing.id)])
    loop_store = AsyncMock()
    loop_store.get = AsyncMock(return_value=existing)
    loop_store.list = AsyncMock(return_value=[])
    result = await find_matching_loop(
        [uuid4()],
        candidate_title,
        loop_store=loop_store,
        graph_store=graph_store,
        embedder=_passport_embedder(),
        **kw,
    )
    return existing, result


async def test_verify_similarity_rejects_a_lone_dissimilar_candidate():
    _, result = await _lone_candidate(
        "buy groceries", "remind me to renew my passport", verify_similarity=True
    )
    assert result is None


async def test_verify_similarity_accepts_a_lone_similar_candidate():
    existing, result = await _lone_candidate(
        "renew passport", "remind me to renew my passport", verify_similarity=True
    )
    assert result is existing


async def test_default_still_returns_a_lone_dissimilar_candidate():
    existing, result = await _lone_candidate(
        "buy groceries", "remind me to renew my passport"
    )
    assert result is existing
