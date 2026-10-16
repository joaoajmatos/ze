"""Fact judge — questions, state, and the decide_fact persist/hold rules."""

from __future__ import annotations

import pytest
from ze_agents.system_one import SystemOneAnswer

from tests.fixtures.fact_gold import PERSIST, make_result
from ze_memory.extractor import KEEP_FAMILIES, PredicateFamily
from ze_memory.fact_judge import FACT_QUESTIONS, FactBars, build_state, decide_fact

_BARS = FactBars(family_hold=0.6, biography_hold=0.7)


def _decide(result, bars=_BARS):
    return decide_fact(
        result.answers.get("family"), result.answers.get("biography"), bars
    )


def test_question_keys():
    assert set(FACT_QUESTIONS) == {"family", "biography"}


def test_family_options_are_keep_families_plus_drop():
    q = FACT_QUESTIONS["family"]
    assert q.type == "choice"
    assert list(q.criteria) == [f.value for f in PredicateFamily] + ["drop"]
    assert set(q.criteria) == KEEP_FAMILIES | {"drop"}


def test_biography_is_noul():
    assert FACT_QUESTIONS["biography"].type == "noul"


def test_build_state_caps_assistant_and_has_only_two_keys():
    state = build_state("hi there", "x" * 1500)
    assert set(state) == {"user", "assistant"}
    assert state["user"] == "hi there"
    assert len(state["assistant"]) == 1000


@pytest.mark.parametrize("turn", PERSIST, ids=lambda t: t.id)
def test_confident_fact_persists_with_chosen_family(turn):
    decision = _decide(turn.result())
    assert decision.kind == "persist"
    assert decision.family == turn.family
    assert decision.consumed == frozenset({"family", "biography"})


@pytest.mark.parametrize("label", ["drop", "ephemeral", "banana"])
def test_drop_or_unknown_family_holds(label):
    decision = _decide(make_result(label))
    assert (decision.kind, decision.reason) == ("hold", "family_drop")
    assert decision.consumed == frozenset({"family"})


def test_unsure_family_holds():
    decision = _decide(make_result("preference", family_confidence=0.4))
    assert (decision.kind, decision.reason) == ("hold", "family_unsure")
    assert decision.consumed == frozenset({"family"})


def test_family_boundary_at_bar_persists():
    assert _decide(make_result("preference", family_confidence=0.6)).kind == "persist"


def test_even_biography_holds_despite_confident_family():
    decision = _decide(make_result("preference", noul=0.5))
    assert (decision.kind, decision.reason) == ("hold", "not_biography")
    assert decision.consumed == frozenset({"family", "biography"})


def test_biography_boundary_at_bar_persists():
    assert _decide(make_result("preference", noul=0.7)).kind == "persist"


def test_bars_are_independent():
    loose_bio = FactBars(family_hold=0.9, biography_hold=0.2)
    assert (
        _decide(make_result("preference", family_confidence=0.8), loose_bio).reason
        == "family_unsure"
    )
    assert _decide(make_result("preference", noul=0.3), loose_bio).kind == "persist"
    loose_family = FactBars(family_hold=0.2, biography_hold=0.9)
    assert (
        _decide(make_result("preference", family_confidence=0.3), loose_family).kind
        == "persist"
    )
    assert (
        _decide(make_result("preference", noul=0.8), loose_family).reason
        == "not_biography"
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda a: a.pop("family"),
        lambda a: a.pop("biography"),
        lambda a: setattr(a["family"], "confidence", None),
        lambda a: setattr(a["family"], "choice", None),
        lambda a: setattr(a["biography"], "noul", None),
        lambda a: a.update(
            biography=SystemOneAnswer(type="choice", choice="x", confidence=0.9)
        ),
    ],
)
def test_malformed_answer_is_skip_invalid_answer(mutate):
    result = make_result("preference")
    mutate(result.answers)
    decision = _decide(result)
    assert (decision.kind, decision.reason) == ("skip", "invalid_answer")
    assert decision.consumed == frozenset()
