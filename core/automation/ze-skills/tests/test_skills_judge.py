from __future__ import annotations

from uuid import uuid4

import pytest

from ze_agents.system_one import SystemOneAnswer, SystemOneResult

from ze_skills.judge import (
    DEFAULT_SHORTLIST_FLOOR,
    DEFAULT_SHORTLIST_K,
    DESCRIPTION_CAP,
    NONE_KEY,
    Q_NEEDS,
    Q_SKILL,
    SkillsSurfaceConfig,
    build_judgment_state_skills,
    build_questions,
    decide,
    shortlist,
    skill_keys,
    skills_surface_config,
)
from ze_skills.types import Skill, SkillSource, SkillStatus


def _skill(name: str, description: str = "does a thing", **kw) -> Skill:
    return Skill(
        name=name,
        description=description,
        instructions="x",
        source=kw.pop("source", SkillSource.IMPORTED),
        status=SkillStatus.ACTIVE,
        id=uuid4(),
        **kw,
    )


def _settings(block) -> dict:
    return {"system_one": {"surfaces": {"skills": block}}}


# ── T003: surface config ────────────────────────────────────────────────


def test_missing_block_is_disabled():
    cfg = skills_surface_config({})
    assert cfg == SkillsSurfaceConfig()
    assert not cfg.enabled and not cfg.calibrated
    assert cfg.shortlist_k == DEFAULT_SHORTLIST_K
    assert cfg.shortlist_floor == DEFAULT_SHORTLIST_FLOOR


def test_non_dict_block_is_disabled():
    assert skills_surface_config(_settings("nope")) == SkillsSurfaceConfig()


def test_enabled_with_null_bar_not_calibrated():
    cfg = skills_surface_config(
        _settings({"enabled": True, "choice_trust": 0.7, "needs_skill_hold": None})
    )
    assert cfg.enabled and not cfg.calibrated


def test_enabled_with_both_bars_calibrated():
    cfg = skills_surface_config(
        _settings({"enabled": True, "choice_trust": 0.7, "needs_skill_hold": 0.5})
    )
    assert cfg.calibrated


def test_settings_object_with_config_attr():
    class S:
        config = _settings(
            {"enabled": True, "choice_trust": 0.6, "needs_skill_hold": 0.4}
        )

    assert skills_surface_config(S()).calibrated


@pytest.mark.parametrize("bad", ["0.5", float("nan"), 1.5, -0.1, True])
def test_bad_bars_become_none(bad):
    cfg = skills_surface_config(
        _settings({"enabled": True, "choice_trust": bad, "needs_skill_hold": bad})
    )
    assert cfg.choice_trust is None and cfg.needs_skill_hold is None


@pytest.mark.parametrize("bad", [0, -1, True, "5", 2.5, None])
def test_bad_shortlist_k_falls_back(bad):
    assert (
        skills_surface_config(_settings({"shortlist_k": bad})).shortlist_k
        == DEFAULT_SHORTLIST_K
    )


def test_valid_shortlist_k():
    assert skills_surface_config(_settings({"shortlist_k": 7})).shortlist_k == 7


@pytest.mark.parametrize("bad", [-0.1, 1.2, "0.3", True, float("nan"), None])
def test_bad_shortlist_floor_falls_back(bad):
    assert (
        skills_surface_config(_settings({"shortlist_floor": bad})).shortlist_floor
        == DEFAULT_SHORTLIST_FLOOR
    )


def test_valid_shortlist_floor():
    assert (
        skills_surface_config(_settings({"shortlist_floor": 0.4})).shortlist_floor
        == 0.4
    )


# ── T003: questions ─────────────────────────────────────────────────────


def test_build_questions_shapes():
    a, b = _skill("Email Tone", "tone for email"), _skill("Meeting Notes", "notes")
    keys = skill_keys([a, b])
    qs = build_questions(keys)
    assert qs[Q_SKILL].type == "choice"
    assert qs[Q_SKILL].criteria["email-tone"] == "tone for email"
    assert qs[Q_SKILL].criteria["meeting-notes"] == "notes"
    assert NONE_KEY in qs[Q_SKILL].criteria
    assert qs[Q_NEEDS].type == "noul"
    assert qs[Q_NEEDS].criteria is None


def test_descriptions_are_capped():
    s = _skill("Long", "x" * (DESCRIPTION_CAP + 100))
    qs = build_questions(skill_keys([s]))
    assert len(qs[Q_SKILL].criteria["long"]) == DESCRIPTION_CAP
    assert len(s.description) == DESCRIPTION_CAP + 100


def test_duplicate_slugs_disambiguated_by_source():
    a = _skill("Same", source=SkillSource.BUNDLED)
    b = _skill("Same", source=SkillSource.IMPORTED)
    keys = skill_keys([a, b])
    assert set(keys) == {"same (bundled)", "same (imported)"}
    assert keys["same (bundled)"].id == a.id
    assert keys["same (imported)"].id == b.id


def test_unique_slugs_stay_plain():
    a, b = _skill("One"), _skill("Two")
    assert set(skill_keys([a, b])) == {"one", "two"}


def test_state_skills_line_list_capped():
    base = {"user": "hi"}
    s = _skill("A", "d" * 5000)
    out = build_judgment_state_skills(base, [s])
    assert out["user"] == "hi"
    assert out["skills"].startswith("a: ") or out["skills"].startswith("A: ")
    assert len(out["skills"]) <= 1500
    assert "skills" not in base


# ── T004: shortlist ─────────────────────────────────────────────────────


def _scored(*pairs):
    return [(_skill(n), s) for n, s in pairs]


def test_shortlist_floor_excludes_and_sorts_desc():
    scored = _scored(("low", 0.2), ("mid", 0.4), ("hi", 0.9))
    out = shortlist(scored, floor=0.35, k=5)
    assert [s.name for s, _ in out] == ["hi", "mid"]


def test_shortlist_k_caps():
    scored = _scored(("a", 0.9), ("b", 0.8), ("c", 0.7))
    assert len(shortlist(scored, floor=0.3, k=2)) == 2


def test_shortlist_empty_is_empty():
    assert shortlist(_scored(("a", 0.1)), floor=0.35, k=5) == []
    assert shortlist([], floor=0.35, k=5) == []


def test_shortlist_stable_tiebreak():
    a, b = _skill("a"), _skill("b")
    out1 = shortlist([(a, 0.5), (b, 0.5)], floor=0.3, k=5)
    out2 = shortlist([(b, 0.5), (a, 0.5)], floor=0.3, k=5)
    assert [s.id for s, _ in out1] == [s.id for s, _ in out2]


# ── T013: decide ────────────────────────────────────────────────────────

CFG = SkillsSurfaceConfig(enabled=True, choice_trust=0.7, needs_skill_hold=0.5)
KEYS = ["email-tone", "meeting-notes"]


def _result(choice="email-tone", peak=0.9, noul=0.8, *, noul_answer=True):
    answers = {Q_SKILL: SystemOneAnswer(type="choice", choice=choice, confidence=peak)}
    if noul_answer:
        answers[Q_NEEDS] = SystemOneAnswer(type="noul", noul=noul)
    return SystemOneResult(outcome="ok", answers=answers)


def test_apply():
    d = decide(_result(), CFG, KEYS)
    assert d.kind == "apply" and d.skill_key == "email-tone"
    assert d.consumed == frozenset({Q_SKILL, Q_NEEDS})


def test_apply_at_exact_bars():
    assert decide(_result(peak=0.7, noul=0.5), CFG, KEYS).kind == "apply"


def test_trusted_none_drops():
    d = decide(_result(choice=NONE_KEY), CFG, KEYS)
    assert d.kind == "drop" and d.reason == "choice_none"
    assert d.consumed == frozenset({Q_SKILL})


def test_noul_below_bar_drops():
    d = decide(_result(noul=0.2), CFG, KEYS)
    assert d.kind == "drop" and d.reason == "not_needed"
    assert d.consumed == frozenset({Q_SKILL, Q_NEEDS})


def test_unsure_choice_abstains_even_for_none():
    for choice in ("email-tone", NONE_KEY):
        d = decide(_result(choice=choice, peak=0.4), CFG, KEYS)
        assert d.kind == "abstain" and d.reason == "choice_unsure"
        assert d.consumed == frozenset()


def test_choice_outside_shortlist_is_invalid():
    d = decide(_result(choice="bogus"), CFG, KEYS)
    assert d.kind == "skip" and d.reason == "invalid_answer"


def test_missing_choice_is_invalid():
    r = SystemOneResult(outcome="ok", answers={})
    assert decide(r, CFG, KEYS).reason == "invalid_answer"


def test_missing_noul_with_named_choice_skips():
    d = decide(_result(noul_answer=False), CFG, KEYS)
    assert d.kind == "skip" and d.reason == "invalid_answer"


def test_choice_without_confidence_invalid():
    r = SystemOneResult(
        outcome="ok",
        answers={Q_SKILL: SystemOneAnswer(type="choice", choice="email-tone")},
    )
    assert decide(r, CFG, KEYS).reason == "invalid_answer"


def test_null_bar_skips_uncalibrated():
    cfg = SkillsSurfaceConfig(enabled=True, choice_trust=0.7)
    d = decide(_result(), cfg, KEYS)
    assert d.kind == "skip" and d.reason == "uncalibrated"


def test_client_skip_carries_reason():
    r = SystemOneResult(outcome="skip", skip_reason="timeout")
    d = decide(r, CFG, KEYS)
    assert d.kind == "skip" and d.reason == "timeout"


def test_decide_never_raises_on_garbage():
    r = SystemOneResult(
        outcome="ok",
        answers={
            Q_SKILL: SystemOneAnswer(type="noul", noul=0.3),
        },
    )
    assert decide(r, CFG, KEYS).kind == "skip"
