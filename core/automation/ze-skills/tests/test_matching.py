from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import numpy as np
import pytest

from ze_skills.matching import SkillMatcher
from ze_skills.types import Skill, SkillSource, SkillStatus, SkillTrigger


def _unit_vec(seed: int, size: int = 8) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(size).astype(np.float32)
    return v / np.linalg.norm(v)


def _skill(name: str, description: str = "does a thing", **overrides) -> Skill:
    defaults = dict(
        name=name,
        description=description,
        instructions="Do the thing.",
        source=SkillSource.IMPORTED,
        status=SkillStatus.ACTIVE,
        id=uuid4(),
    )
    defaults.update(overrides)
    return Skill(**defaults)


def _make_embedder(passage_vec: np.ndarray, query_vec: np.ndarray) -> MagicMock:
    """Mocked embedder mirroring `EmbeddingRouter`'s `encode_query`/`encode_passage`
    contract — `encode_passage` always returns a batch (even for one item)."""
    embedder = MagicMock()
    embedder.encode_passage.side_effect = lambda texts, **kw: np.stack([passage_vec])
    embedder.encode_query.side_effect = lambda text, **kw: query_vec
    return embedder


def _make_store(skills: list[Skill]) -> AsyncMock:
    store = AsyncMock()
    store.list_active = AsyncMock(return_value=skills)
    return store


@pytest.mark.asyncio
async def test_automatic_match_above_threshold():
    vec = _unit_vec(1)
    skill = _skill("Pirate Speak")
    store = _make_store([skill])
    embedder = _make_embedder(passage_vec=vec, query_vec=vec)  # identical -> sim=1.0
    matcher = SkillMatcher(store=store, embedder=embedder, match_threshold=0.5)

    matches = await matcher.match("talk like a pirate")

    assert len(matches) == 1
    assert matches[0].skill.id == skill.id
    assert matches[0].trigger == SkillTrigger.AUTOMATIC
    assert matches[0].similarity == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_automatic_match_below_threshold_excluded():
    passage_vec = _unit_vec(1)
    query_vec = -_unit_vec(1)  # opposite direction -> similarity -1.0
    skill = _skill("Pirate Speak")
    store = _make_store([skill])
    embedder = _make_embedder(passage_vec=passage_vec, query_vec=query_vec)
    matcher = SkillMatcher(store=store, embedder=embedder, match_threshold=0.5)

    matches = await matcher.match("something unrelated")

    assert matches == []


@pytest.mark.asyncio
async def test_explicit_invocation_parsed_and_takes_precedence():
    passage_vec = _unit_vec(1)
    query_vec = -_unit_vec(1)  # would NOT match automatically
    skill = _skill("Pirate Speak")
    store = _make_store([skill])
    embedder = _make_embedder(passage_vec=passage_vec, query_vec=query_vec)
    matcher = SkillMatcher(store=store, embedder=embedder, match_threshold=0.5)

    matches = await matcher.match(f"/{skill.slug} say something")

    assert len(matches) == 1
    assert matches[0].trigger == SkillTrigger.EXPLICIT
    assert matches[0].similarity is None


@pytest.mark.asyncio
async def test_explicit_invocation_unknown_slug_has_no_match():
    skill = _skill("Pirate Speak")
    store = _make_store([skill])
    embedder = _make_embedder(passage_vec=_unit_vec(1), query_vec=-_unit_vec(1))
    matcher = SkillMatcher(store=store, embedder=embedder, match_threshold=0.5)

    matches = await matcher.match("/not-a-real-skill do something")

    assert matches == []


@pytest.mark.asyncio
async def test_combined_automatic_and_explicit_matches_in_one_turn():
    auto_vec = _unit_vec(2)
    explicit_skill = _skill("Formal Tone", description="be formal")
    auto_skill = _skill("Emoji Mode", description="add emojis")

    store = AsyncMock()
    store.list_active = AsyncMock(return_value=[explicit_skill, auto_skill])

    embedder = MagicMock()

    def encode_passage(texts, **kw):
        # Both skills' passages score identically for simplicity — only the
        # auto_skill actually reaches embedding scoring since explicit_skill
        # is resolved via slug first.
        return np.stack([auto_vec for _ in texts])

    embedder.encode_passage.side_effect = encode_passage
    embedder.encode_query.side_effect = lambda text, **kw: auto_vec

    matcher = SkillMatcher(store=store, embedder=embedder, match_threshold=0.5)

    matches = await matcher.match(
        f"/{explicit_skill.slug} please, and check emojis too"
    )

    triggers = {m.skill.id: m.trigger for m in matches}
    assert triggers[explicit_skill.id] == SkillTrigger.EXPLICIT
    assert triggers[auto_skill.id] == SkillTrigger.AUTOMATIC


@pytest.mark.asyncio
async def test_no_active_skills_returns_empty():
    store = _make_store([])
    embedder = MagicMock()
    matcher = SkillMatcher(store=store, embedder=embedder, match_threshold=0.5)

    matches = await matcher.match("anything")

    assert matches == []
    embedder.encode_query.assert_not_called()


@pytest.mark.asyncio
async def test_embedding_cache_invalidated_on_content_hash_change():
    skill = _skill("Pirate Speak")
    store = _make_store([skill])
    vec = _unit_vec(1)
    embedder = _make_embedder(passage_vec=vec, query_vec=vec)
    matcher = SkillMatcher(store=store, embedder=embedder, match_threshold=0.5)

    await matcher.match("talk like a pirate")
    assert embedder.encode_passage.call_count == 1

    # Same skill, same content_hash — cache hit, no re-embed.
    await matcher.match("talk like a pirate again")
    assert embedder.encode_passage.call_count == 1

    # Content changed — new content_hash, cache miss, re-embed.
    skill.description = "a totally different description"
    skill.content_hash = "changed-hash"
    await matcher.match("talk like a pirate once more")
    assert embedder.encode_passage.call_count == 2
