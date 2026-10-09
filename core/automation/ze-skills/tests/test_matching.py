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

    matches = (await matcher.match("talk like a pirate")).matches

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

    matches = (await matcher.match("something unrelated")).matches

    assert matches == []


@pytest.mark.asyncio
async def test_explicit_invocation_parsed_and_takes_precedence():
    passage_vec = _unit_vec(1)
    query_vec = -_unit_vec(1)  # would NOT match automatically
    skill = _skill("Pirate Speak")
    store = _make_store([skill])
    embedder = _make_embedder(passage_vec=passage_vec, query_vec=query_vec)
    matcher = SkillMatcher(store=store, embedder=embedder, match_threshold=0.5)

    matches = (await matcher.match(f"/{skill.slug} say something")).matches

    assert len(matches) == 1
    assert matches[0].trigger == SkillTrigger.EXPLICIT
    assert matches[0].similarity is None


@pytest.mark.asyncio
async def test_explicit_invocation_unknown_slug_has_no_match():
    skill = _skill("Pirate Speak")
    store = _make_store([skill])
    embedder = _make_embedder(passage_vec=_unit_vec(1), query_vec=-_unit_vec(1))
    matcher = SkillMatcher(store=store, embedder=embedder, match_threshold=0.5)

    matches = (await matcher.match("/not-a-real-skill do something")).matches

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

    matches = (
        await matcher.match(f"/{explicit_skill.slug} please, and check emojis too")
    ).matches

    triggers = {m.skill.id: m.trigger for m in matches}
    assert triggers[explicit_skill.id] == SkillTrigger.EXPLICIT
    assert triggers[auto_skill.id] == SkillTrigger.AUTOMATIC


@pytest.mark.asyncio
async def test_no_active_skills_returns_empty():
    store = _make_store([])
    embedder = MagicMock()
    matcher = SkillMatcher(store=store, embedder=embedder, match_threshold=0.5)

    matches = (await matcher.match("anything")).matches

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


# ── Phase 166: System One gating ────────────────────────────────────────

import math  # noqa: E402

from ze_agents.system_one import SystemOneAnswer, SystemOneResult  # noqa: E402

from ze_skills.judge import Q_NEEDS, Q_SKILL, SkillsSurfaceConfig  # noqa: E402

_QUERY = np.array([1.0, 0.0], dtype=np.float32)


def _vec_for_sim(sim: float) -> np.ndarray:
    return np.array([sim, math.sqrt(1 - sim * sim)], dtype=np.float32)


class _SimEmbedder:
    """Passage vector per `name: description` text so each skill gets a chosen cosine."""

    def __init__(self, sims: dict[str, float]) -> None:
        self._sims = sims
        self.query_calls = 0

    def encode_query(self, text, **kw):
        self.query_calls += 1
        return _QUERY

    def encode_passage(self, texts, **kw):
        return np.stack([_vec_for_sim(self._sims[t.split(":")[0]]) for t in texts])


class _FakeClient:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple] = []

    async def evaluate(self, state, questions, *, max_attempts=None):
        self.calls.append((state, questions, max_attempts))
        if self.error:
            raise self.error
        return self.result


def _ok(choice: str, peak: float = 0.9, noul: float | None = 0.8) -> SystemOneResult:
    answers = {Q_SKILL: SystemOneAnswer(type="choice", choice=choice, confidence=peak)}
    if noul is not None:
        answers[Q_NEEDS] = SystemOneAnswer(type="noul", noul=noul)
    return SystemOneResult(outcome="ok", answers=answers)


_CAL = SkillsSurfaceConfig(
    enabled=True,
    choice_trust=0.7,
    needs_skill_hold=0.5,
    shortlist_k=5,
    shortlist_floor=0.35,
)
_STATE = {"user": "write an email"}


def _gated(sims: dict[str, float], client, surface=_CAL):
    skills = [_skill(name) for name in sims]
    embedder = _SimEmbedder(sims)
    matcher = SkillMatcher(
        store=_make_store(skills),
        embedder=embedder,
        match_threshold=0.5,
        system_one_client=client,
        surface=surface,
    )
    return matcher, skills, embedder


def _autos(outcome):
    return [m for m in outcome.matches if m.trigger == SkillTrigger.AUTOMATIC]


@pytest.mark.asyncio
async def test_trusted_choice_applies_exactly_one_of_two_above_floor():
    client = _FakeClient(_ok("email-tone"))
    matcher, skills, _ = _gated({"Email Tone": 0.7, "Meeting Notes": 0.65}, client)

    outcome = await matcher.match("write an email", judgment_state=_STATE)

    autos = _autos(outcome)
    assert [m.skill.name for m in autos] == ["Email Tone"]
    assert autos[0].below_floor is False
    assert outcome.judgment.consumed == frozenset({Q_SKILL, Q_NEEDS})


@pytest.mark.asyncio
async def test_request_shape():
    client = _FakeClient(_ok("email-tone"))
    matcher, _, _ = _gated({"Email Tone": 0.7, "Meeting Notes": 0.65}, client)

    await matcher.match("write an email", judgment_state=_STATE)

    state, questions, max_attempts = client.calls[0]
    assert max_attempts == 1
    assert set(questions[Q_SKILL].criteria) == {"email-tone", "meeting-notes", "none"}
    assert state["user"] == "write an email"
    assert "Email Tone" in state["skills"]


@pytest.mark.asyncio
async def test_choice_none_applies_no_automatic_skill():
    client = _FakeClient(_ok("none"))
    matcher, _, _ = _gated({"Email Tone": 0.7}, client)

    outcome = await matcher.match("hello", judgment_state=_STATE)

    assert outcome.matches == []
    assert outcome.judgment.consumed == frozenset({Q_SKILL})


@pytest.mark.asyncio
async def test_noul_below_bar_applies_nothing():
    client = _FakeClient(_ok("email-tone", noul=0.1))
    matcher, _, _ = _gated({"Email Tone": 0.7}, client)

    outcome = await matcher.match("hello", judgment_state=_STATE)

    assert outcome.matches == []


@pytest.mark.asyncio
async def test_explicit_stacks_with_judged_automatic():
    client = _FakeClient(_ok("email-tone"))
    matcher, skills, _ = _gated({"Email Tone": 0.7, "Meeting Notes": 0.1}, client)

    outcome = await matcher.match(
        "/meeting-notes write an email", judgment_state=_STATE
    )

    by_trigger = {m.trigger: m.skill.name for m in outcome.matches}
    assert by_trigger == {
        SkillTrigger.EXPLICIT: "Meeting Notes",
        SkillTrigger.AUTOMATIC: "Email Tone",
    }
    # the explicit skill is not a Choice option
    assert "meeting-notes" not in client.calls[0][1][Q_SKILL].criteria


@pytest.mark.asyncio
async def test_explicit_only_turn_makes_no_request():
    client = _FakeClient(_ok("none"))
    matcher, _, _ = _gated({"Email Tone": 0.7}, client)

    outcome = await matcher.match("/email-tone hi", judgment_state=_STATE)

    assert client.calls == []
    assert [m.trigger for m in outcome.matches] == [SkillTrigger.EXPLICIT]
    assert outcome.judgment is None


@pytest.mark.asyncio
async def test_no_request_when_shortlist_empty():
    client = _FakeClient(_ok("none"))
    matcher, _, _ = _gated({"Email Tone": 0.1}, client)

    outcome = await matcher.match("hello", judgment_state=_STATE)

    assert client.calls == [] and outcome.matches == [] and outcome.judgment is None


@pytest.mark.asyncio
async def test_query_encoded_once_per_call():
    client = _FakeClient(_ok("email-tone"))
    matcher, _, embedder = _gated({"Email Tone": 0.7, "Meeting Notes": 0.65}, client)

    await matcher.match("write an email", judgment_state=_STATE)

    assert embedder.query_calls == 1


@pytest.mark.asyncio
async def test_duplicate_slugs_resolve_to_one_skill():
    a = _skill("Same", source=SkillSource.BUNDLED)
    b = _skill("Same", source=SkillSource.IMPORTED)
    embedder = _SimEmbedder({"Same": 0.7})
    client = _FakeClient(_ok("same (imported)"))
    matcher = SkillMatcher(
        store=_make_store([a, b]),
        embedder=embedder,
        system_one_client=client,
        surface=_CAL,
    )

    outcome = await matcher.match("x", judgment_state=_STATE)

    assert [m.skill.id for m in _autos(outcome)] == [b.id]


# ── US2: below the floor ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_below_floor_skill_applies_and_is_marked():
    client = _FakeClient(_ok("email-tone"))
    matcher, _, _ = _gated({"Email Tone": 0.43}, client)

    outcome = await matcher.match("paraphrase", judgment_state=_STATE)

    autos = _autos(outcome)
    assert len(autos) == 1
    assert autos[0].below_floor is True
    assert autos[0].similarity == pytest.approx(0.43, abs=1e-4)


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [_ok("none"), _ok("email-tone", peak=0.3)])
async def test_below_floor_skill_not_applied_on_none_or_unsure(result):
    matcher, _, _ = _gated({"Email Tone": 0.43}, _FakeClient(result))

    outcome = await matcher.match("paraphrase", judgment_state=_STATE)

    assert outcome.matches == []


@pytest.mark.asyncio
async def test_skill_under_shortlist_floor_never_listed_or_applied():
    client = _FakeClient(_ok("none"))
    matcher, _, _ = _gated({"Email Tone": 0.3, "Meeting Notes": 0.45}, client)

    outcome = await matcher.match("x", judgment_state=_STATE)

    assert set(client.calls[0][1][Q_SKILL].criteria) == {"meeting-notes", "none"}
    assert outcome.matches == []


def test_floor_above_threshold_is_clamped():
    surface = SkillsSurfaceConfig(
        enabled=True, choice_trust=0.7, needs_skill_hold=0.5, shortlist_floor=0.9
    )
    matcher = SkillMatcher(
        store=_make_store([]),
        embedder=MagicMock(),
        match_threshold=0.5,
        surface=surface,
    )
    assert matcher._floor == 0.5


# ── US3: parity on every non-judged path ────────────────────────────────

_SIMS = {"Email Tone": 0.7, "Meeting Notes": 0.65, "Low": 0.2}


async def _legacy(sims):
    matcher = SkillMatcher(
        store=_make_store([_skill(n) for n in sims]),
        embedder=_SimEmbedder(sims),
        match_threshold=0.5,
    )
    return {m.skill.name for m in (await matcher.match("x")).matches}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "surface,client",
    [
        (SkillsSurfaceConfig(), _FakeClient(_ok("none"))),  # disabled
        (SkillsSurfaceConfig(enabled=True), _FakeClient(_ok("none"))),  # uncalibrated
        (_CAL, _FakeClient(SystemOneResult(outcome="skip", skip_reason="timeout"))),
        (_CAL, _FakeClient(error=RuntimeError("boom"))),
        (_CAL, _FakeClient(_ok("not-a-listed-skill"))),
        (_CAL, _FakeClient(_ok("none", peak=0.2))),  # unsure
        (_CAL, _FakeClient(_ok("email-tone", noul=None))),  # missing noul
    ],
    ids=["off", "uncalibrated", "skip", "exception", "invalid", "unsure", "no_noul"],
)
async def test_non_judged_paths_equal_114(surface, client):
    expected = await _legacy(_SIMS)
    matcher, _, _ = _gated(_SIMS, client, surface)

    outcome = await matcher.match("x", judgment_state=_STATE)

    assert (
        {m.skill.name for m in outcome.matches}
        == expected
        == {"Email Tone", "Meeting Notes"}
    )
    assert all(not m.below_floor for m in outcome.matches)
    if surface.calibrated:
        assert outcome.judgment is not None
        assert outcome.judgment.consumed == frozenset()
    else:
        assert client.calls == [] and outcome.judgment is None


@pytest.mark.asyncio
async def test_invalid_answer_judgment_carries_skip_reason():
    matcher, _, _ = _gated(_SIMS, _FakeClient(_ok("bogus")))
    outcome = await matcher.match("x", judgment_state=_STATE)
    assert outcome.judgment.skip_reason == "invalid_answer"


@pytest.mark.asyncio
async def test_client_exception_yields_error_skip_judgment():
    matcher, _, _ = _gated(_SIMS, _FakeClient(error=RuntimeError("boom")))
    outcome = await matcher.match("x", judgment_state=_STATE)
    assert outcome.judgment.result.outcome == "skip"
    assert outcome.judgment.result.skip_reason == "error"


@pytest.mark.asyncio
async def test_no_judgment_state_means_no_request():
    client = _FakeClient(_ok("none"))
    matcher, _, _ = _gated(_SIMS, client)
    outcome = await matcher.match("x")
    assert client.calls == [] and outcome.judgment is None
