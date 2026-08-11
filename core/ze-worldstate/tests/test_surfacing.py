from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_worldstate.surfacing import LoopSurfacer, format_hedged_mention
from ze_worldstate.types import LoopClaimKind, LoopProvenance, LoopState, OpenLoop


def _loop(**overrides) -> OpenLoop:
    base = dict(
        id=uuid4(),
        title="Send Maria the contract",
        claim_kind=LoopClaimKind.PRIORITY,
        provenance=LoopProvenance.USER_DECLARED,
        confidence=0.5,
        state=LoopState.DRIFTING,
        drift_rationale="No corroborating evidence since confirmation on 2026-07-10.",
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


def _surfacer(loop_store, graph_store, push_log=None) -> LoopSurfacer:
    return LoopSurfacer(
        loop_store=loop_store,
        graph_store=graph_store,
        push_log=push_log or AsyncMock(),
    )


def test_format_hedged_mention_starts_with_hedge_prefix():
    text = format_hedged_mention("Renew passport", "Deadline elapsed.")
    assert text.startswith("It looks like")
    assert "Renew passport" in text
    assert "Deadline elapsed." in text


def test_format_hedged_mention_without_rationale():
    text = format_hedged_mention("Renew passport", None)
    assert text.startswith("It looks like")
    assert text.endswith(".")


async def test_entity_overlap_surfaces_a_mention():
    loop = _loop()
    graph_store = AsyncMock()
    graph_store.list_relationships = AsyncMock(return_value=[_rel(loop.id)])
    loop_store = AsyncMock()
    loop_store.get = AsyncMock(return_value=loop)
    loop_store.list_evidence = AsyncMock(return_value=[])
    push_log = AsyncMock()

    surfacer = _surfacer(loop_store, graph_store, push_log)
    mentions = await surfacer.inline_candidates([uuid4()])

    assert len(mentions) == 1
    assert mentions[0].loop_id == loop.id
    assert mentions[0].mention_text.startswith("It looks like")
    push_log.log.assert_awaited_once_with(f"worldstate_loop_inline:{loop.id}")


async def test_no_overlap_produces_no_mention():
    graph_store = AsyncMock()
    graph_store.list_relationships = AsyncMock(return_value=[])
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[])

    surfacer = _surfacer(loop_store, graph_store)
    mentions = await surfacer.inline_candidates([uuid4()])

    assert mentions == []


async def test_non_drifting_linked_loop_is_not_surfaced():
    loop = _loop(state=LoopState.ACTIVE)
    graph_store = AsyncMock()
    graph_store.list_relationships = AsyncMock(return_value=[_rel(loop.id)])
    loop_store = AsyncMock()
    loop_store.get = AsyncMock(return_value=loop)

    surfacer = _surfacer(loop_store, graph_store)
    mentions = await surfacer.inline_candidates([uuid4()])

    assert mentions == []


async def test_repeated_relevant_turns_may_mention_again():
    """No novelty/budget gate on inline (FR-006) — every call re-surfaces."""
    loop = _loop()
    graph_store = AsyncMock()
    graph_store.list_relationships = AsyncMock(return_value=[_rel(loop.id)])
    loop_store = AsyncMock()
    loop_store.get = AsyncMock(return_value=loop)
    loop_store.list_evidence = AsyncMock(return_value=[])
    push_log = AsyncMock()

    surfacer = _surfacer(loop_store, graph_store, push_log)
    first = await surfacer.inline_candidates([uuid4()])
    second = await surfacer.inline_candidates([uuid4()])

    assert len(first) == 1
    assert len(second) == 1
    assert push_log.log.await_count == 2


async def test_no_entity_ids_returns_empty_without_query():
    graph_store = AsyncMock()
    loop_store = AsyncMock()
    surfacer = _surfacer(loop_store, graph_store)

    mentions = await surfacer.inline_candidates([])

    assert mentions == []
    graph_store.list_relationships.assert_not_awaited()


# ── passes_push_bar (T032, T038) ───────────────────────────────────────────────


def _relevance_model(value: float = 0.8) -> MagicMock:
    model = MagicMock()
    model.build = AsyncMock(return_value=object())
    model.score = MagicMock(return_value=SimpleNamespace(value=value, contributions=[]))
    return model


def _push_bar_surfacer(
    *,
    relevance_value: float = 0.8,
    recent_payloads: list[str] | None = None,
    inline_sent: bool = False,
    budget_count: int = 0,
) -> LoopSurfacer:
    push_log = AsyncMock()
    push_log.list_recent_payloads = AsyncMock(return_value=recent_payloads or [])
    push_log.was_sent_within_hours = AsyncMock(return_value=inline_sent)
    push_log.count_sent_within_hours = AsyncMock(return_value=budget_count)
    push_log.log = AsyncMock()

    return LoopSurfacer(
        loop_store=AsyncMock(),
        graph_store=AsyncMock(),
        push_log=push_log,
        pool=None,
        relevance_model=_relevance_model(relevance_value),
        embedder=None,
    )


async def test_passes_push_bar_clears_all_gates():
    loop = _loop(confidence=0.8)
    surfacer = _push_bar_surfacer(relevance_value=0.8)
    assert await surfacer.passes_push_bar(loop, loop.drift_rationale) is True


async def test_passes_push_bar_rejects_low_confidence():
    loop = _loop(confidence=0.1)
    surfacer = _push_bar_surfacer()
    assert await surfacer.passes_push_bar(loop, loop.drift_rationale) is False


async def test_passes_push_bar_rejects_low_relevance():
    loop = _loop(confidence=0.8)
    surfacer = _push_bar_surfacer(relevance_value=0.1)
    assert await surfacer.passes_push_bar(loop, loop.drift_rationale) is False


async def test_passes_push_bar_rejects_budget_exhausted():
    loop = _loop(confidence=0.8)
    surfacer = _push_bar_surfacer(relevance_value=0.8, budget_count=3)
    assert (
        await surfacer.passes_push_bar(loop, loop.drift_rationale, max_pushes_per_day=3)
        is False
    )


async def test_passes_push_bar_rejects_within_inline_cooldown():
    loop = _loop(confidence=0.8)
    surfacer = _push_bar_surfacer(relevance_value=0.8, inline_sent=True)
    assert await surfacer.passes_push_bar(loop, loop.drift_rationale) is False


async def test_claim_push_calls_try_claim_with_loop_id_as_idempotency_key():
    push_log = AsyncMock()
    push_log.try_claim = AsyncMock(return_value=True)
    surfacer = LoopSurfacer(
        loop_store=AsyncMock(), graph_store=AsyncMock(), push_log=push_log
    )
    loop_id = uuid4()
    result = await surfacer.claim_push(loop_id, "rationale text")
    assert result is True
    push_log.try_claim.assert_awaited_once_with(
        "worldstate_loop_push", idempotency_key=str(loop_id), payload="rationale text"
    )


async def test_release_push_claim_calls_release_claim():
    push_log = AsyncMock()
    surfacer = LoopSurfacer(
        loop_store=AsyncMock(), graph_store=AsyncMock(), push_log=push_log
    )
    loop_id = uuid4()
    await surfacer.release_push_claim(loop_id)
    push_log.release_claim.assert_awaited_once_with(
        "worldstate_loop_push", idempotency_key=str(loop_id)
    )
