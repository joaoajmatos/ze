"""Commitment intake judge — questions, config, and every row of the decision table."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from ze_agents.nested_tools import TurnCreation
from ze_agents.system_one import SystemOneAnswer, SystemOneResult

from tests.commitment_fixtures import _BARS, _CAL, _LABELS, _NONE, make
from ze_worldstate.commitment_judge import (
    COMMITMENT_QUESTIONS,
    CommitmentIntakeSurfaceConfig,
    build_state,
    commitment_intake_surface_config,
    decide,
)


def _d(result, *, created=_NONE, tracked=False, cfg=_CAL):
    return decide(result, cfg, created, tracked)


# ── config ───────────────────────────────────────────────────────────────────


def _block(**kw):
    return {"system_one": {"surfaces": {"commitment_intake": kw}}}


def test_missing_block_is_disabled():
    assert commitment_intake_surface_config({}) == CommitmentIntakeSurfaceConfig()
    assert not commitment_intake_surface_config({}).calibrated


def test_calibrated_needs_enabled_and_all_six_bars():
    assert commitment_intake_surface_config(_block(enabled=True, **_BARS)).calibrated
    assert not commitment_intake_surface_config(
        _block(enabled=False, **_BARS)
    ).calibrated
    for name in _BARS:
        partial = {**_BARS, name: None}
        assert not commitment_intake_surface_config(
            _block(enabled=True, **partial)
        ).calibrated


@pytest.mark.parametrize("bad", [1.5, -0.1, "high", True, float("nan")])
def test_bad_bar_becomes_none(bad):
    cfg = commitment_intake_surface_config(
        _block(enabled=True, **{**_BARS, "loop_hold": bad})
    )
    assert cfg.loop_hold is None
    assert not cfg.calibrated


def test_accepts_object_with_config_dict():
    settings = SimpleNamespace(config=_block(enabled=True, **_BARS))
    assert commitment_intake_surface_config(settings).calibrated


def test_none_settings_is_disabled():
    assert not commitment_intake_surface_config(None).enabled


# ── questions ────────────────────────────────────────────────────────────────


def test_question_ids_and_types():
    assert {k: q.type for k, q in COMMITMENT_QUESTIONS.items()} == {
        "commitment": "choice",
        "family": "choice",
        "biography": "noul",
        "is_open_concern": "noul",
        "explicit_declaration": "noul",
        "resolves_existing": "noul",
    }


def test_commitment_options_follow_enum_order():
    assert list(COMMITMENT_QUESTIONS["commitment"].criteria) == _LABELS


def test_criteria_are_filled_and_bilingual():
    criteria = COMMITMENT_QUESTIONS["commitment"].criteria
    for label, text in criteria.items():
        assert text.strip(), label
    joined = " ".join(criteria.values())
    for pt in ("lembra-me", "esquece", "prefiro", "preciso de"):
        assert pt in joined


def test_goal_and_loop_criteria_break_the_deadline_task_tie():
    criteria = COMMITMENT_QUESTIONS["commitment"].criteria
    assert "even if it takes weeks" in criteria["loop"]
    assert "one-off task" in criteria["goal"] and "loop" in criteria["goal"]
    assert "frames" in criteria["goal"]


def test_clarify_criterion_names_the_bare_pointer_cases():
    text = COMMITMENT_QUESTIONS["commitment"].criteria["clarify"]
    for marker in ("'that'", "'it'", "'isso'", "'aquilo'", "no object"):
        assert marker in text


def test_resolves_question_ignores_save_and_remember_requests():
    q = COMMITMENT_QUESTIONS["resolves_existing"]
    assert q.type == "noul"
    for word in ("save", "import", "remember"):
        assert word in q.instructions
    assert "past" in q.instructions


def test_resolves_question_excludes_waiting_statements():
    text = COMMITMENT_QUESTIONS["resolves_existing"].instructions
    assert "waiting" in text and "not" in text


def test_concern_question_counts_keep_an_eye_on_requests():
    text = COMMITMENT_QUESTIONS["is_open_concern"].instructions
    assert "keep an eye on" in text and "lose track" in text


def test_loop_criterion_takes_keep_an_eye_on_with_an_object():
    loop = COMMITMENT_QUESTIONS["commitment"].criteria["loop"]
    assert "'keep an eye on the" in loop and "lose track" in loop


def test_fact_with_a_question_still_reads_as_fact():
    criteria = COMMITMENT_QUESTIONS["commitment"].criteria
    assert "also asks" in criteria["fact"]
    assert "also asks" in criteria["none"]
    assert "A pure question is never a fact" in criteria["fact"]
    assert "Only a statement" not in criteria["fact"]


def test_other_inflow_loop_wording_is_untouched():
    from ze_worldstate.loop_judge import LOOP_QUESTIONS

    assert "save" not in LOOP_QUESTIONS["resolves_existing"].instructions
    assert "keep an eye on" not in LOOP_QUESTIONS["is_open_concern"].instructions


def test_state_is_user_and_capped_assistant():
    state = build_state("hi", "x" * 1500)
    assert set(state) == {"user", "assistant"}
    assert len(state["assistant"]) == 1000


# ── rows 1-3: fallback ───────────────────────────────────────────────────────


def test_row1_skip_is_fallback_with_reason():
    out = _d(SystemOneResult(outcome="skip", skip_reason="timeout"))
    assert (out.kind, out.reason) == ("fallback", "timeout")


def test_row1_skip_without_reason_is_error():
    assert _d(SystemOneResult(outcome="skip")).reason == "error"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda a: a.pop("commitment"),
        lambda a: a.pop("resolves_existing"),
        lambda a: setattr(a["commitment"], "confidence", None),
        lambda a: setattr(a["commitment"], "choice", "banana"),
        lambda a: setattr(a["resolves_existing"], "noul", None),
        lambda a: a.update(
            resolves_existing=SystemOneAnswer(type="choice", choice="x", confidence=0.9)
        ),
    ],
)
def test_row2_malformed_always_needed_answer_falls_back(mutate):
    result = make("loop")
    mutate(result.answers)
    out = _d(result)
    assert (out.kind, out.reason) == ("fallback", "invalid_answer")


@pytest.mark.parametrize(
    ("choice", "drop"),
    [
        ("loop", "is_open_concern"),
        ("loop", "explicit_declaration"),
        ("fact", "family"),
        ("fact", "biography"),
    ],
)
def test_row2_missing_choice_specific_answer_falls_back(choice, drop):
    result = make(choice)
    result.answers.pop(drop)
    out = _d(result)
    assert (out.kind, out.reason) == ("fallback", "invalid_answer")


def test_row2_unneeded_answers_may_be_missing():
    result = make("none")
    for qid in ("family", "biography", "is_open_concern", "explicit_declaration"):
        result.answers.pop(qid)
    assert _d(result).kind == "hold"


@pytest.mark.parametrize("bar", list(_BARS))
def test_row3_any_null_bar_is_uncalibrated_fallback(bar):
    cfg = CommitmentIntakeSurfaceConfig(enabled=True, **{**_BARS, bar: None})
    out = _d(make("loop"), cfg=cfg)
    assert (out.kind, out.reason) == ("fallback", "uncalibrated")


# ── row 4: resolve ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "choice", [label for label in _LABELS if label != "waiting_on"]
)
def test_row4_resolves_whatever_the_choice_but_waiting_on(choice):
    out = _d(make(choice, resolves=0.9))
    assert (out.kind, out.reason) == ("resolve_loop", "resolves")
    assert out.consumed == frozenset({"resolves_existing"})


@pytest.mark.parametrize("resolves", [0.85, 0.99])
def test_row4_waiting_on_never_resolves(resolves):
    out = _d(make("waiting_on", resolves=resolves))
    assert (out.kind, out.reason) == ("hold", "waiting_on")
    assert out.consumed == frozenset({"commitment", "resolves_existing"})


def test_row4_unsure_waiting_on_never_resolves_either():
    out = _d(make("waiting_on", conf=0.2, resolves=0.95))
    assert (out.kind, out.reason) == ("hold", "waiting_on")


def test_row4_waiting_on_with_a_created_id_still_links():
    out = _d(make("waiting_on", resolves=0.95), created=TurnCreation(goal_id="g1"))
    assert (out.kind, out.link_kind) == ("link", "goal")


def test_row4_boundary_at_bar_resolves_below_does_not():
    assert _d(make("none", resolves=0.85)).kind == "resolve_loop"
    assert _d(make("none", resolves=0.8499)).kind == "hold"


def test_row4_resolve_outranks_turn_created():
    out = _d(make("reminder", resolves=0.9), created=TurnCreation(reminder_id="r1"))
    assert out.kind == "resolve_loop"


# ── row 5: link ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("choice", _LABELS)
def test_row5_created_reminder_links_whatever_the_choice(choice):
    out = _d(make(choice), created=TurnCreation(reminder_id="r1"))
    assert (out.kind, out.reason, out.link_kind) == ("link", "turn_created", "reminder")
    assert out.consumed == frozenset({"commitment", "resolves_existing"})


def test_row5_created_goal_links_as_goal():
    out = _d(make("goal"), created=TurnCreation(goal_id="g1"))
    assert (out.kind, out.link_kind) == ("link", "goal")


def test_row5_both_created_records_both_kinds():
    out = _d(make("loop"), created=TurnCreation(reminder_id="r1", goal_id="g1"))
    assert (out.kind, out.link_kind) == ("link", "reminder+goal")


def test_row5_created_beats_fact_label_and_persists_no_fact():
    out = _d(make("fact"), created=TurnCreation(reminder_id="r1"))
    assert out.kind == "link"
    assert out.family is None


def test_row5_created_beats_tracked():
    assert (
        _d(make("loop"), created=TurnCreation(goal_id="g1"), tracked=True).kind
        == "link"
    )


# ── rows 6, 7, 9, choice_unsure: hold ────────────────────────────────────────


@pytest.mark.parametrize("conf", [0.99, 0.1])
def test_row6_waiting_on_holds_at_any_confidence(conf):
    out = _d(make("waiting_on", conf=conf))
    assert (out.kind, out.reason) == ("hold", "waiting_on")
    assert out.consumed == frozenset({"commitment", "resolves_existing"})


@pytest.mark.parametrize("choice", ["reminder", "goal"])
@pytest.mark.parametrize("conf", [0.99, 0.6])
def test_row7_reminder_or_goal_at_or_above_bar_not_created_holds(choice, conf):
    out = _d(make(choice, conf=conf, concern=0.99, explicit=0.99))
    assert (out.kind, out.reason) == ("hold", f"{choice}_not_created")
    assert out.consumed == frozenset({"commitment", "resolves_existing"})


# ── row 7a: unsure reminder or goal with nothing created falls through to the loop rules ──


@pytest.mark.parametrize("choice", ["reminder", "goal"])
def test_row7a_bar_edge_holds_at_bar_and_falls_through_below(choice):
    at = _d(make(choice, conf=0.6, concern=0.9, explicit=0.9))
    below = _d(make(choice, conf=0.5999, concern=0.9, explicit=0.9))
    assert at.reason == f"{choice}_not_created"
    assert (below.kind, below.reason) == ("create_loop_declared", "explicit")


@pytest.mark.parametrize("choice", ["reminder", "goal"])
def test_row7a_falls_through_to_declared(choice):
    out = _d(make(choice, conf=0.3, concern=0.9, explicit=0.9))
    assert (out.kind, out.reason) == ("create_loop_declared", "explicit")
    assert out.consumed == frozenset(
        {"commitment", "resolves_existing", "is_open_concern", "explicit_declaration"}
    )


@pytest.mark.parametrize("choice", ["reminder", "goal"])
def test_row7a_falls_through_to_suspected(choice):
    out = _d(make(choice, conf=0.3, concern=0.9, explicit=0.1))
    assert (out.kind, out.reason) == ("create_loop_suspected", "implied")


@pytest.mark.parametrize("choice", ["reminder", "goal"])
def test_row7a_falls_through_to_not_open_concern(choice):
    out = _d(make(choice, conf=0.3, concern=0.1, explicit=0.9))
    assert (out.kind, out.reason) == ("hold", "not_open_concern")


@pytest.mark.parametrize("choice", ["reminder", "goal"])
def test_row7a_tracked_still_holds(choice):
    out = _d(make(choice, conf=0.3, concern=0.9, explicit=0.9), tracked=True)
    assert (out.kind, out.reason) == ("hold", "tracked")


@pytest.mark.parametrize("choice", ["reminder", "goal"])
def test_row7a_never_reports_loop_unsure(choice):
    assert _d(make(choice, conf=0.0, concern=0.9, explicit=0.9)).reason != "loop_unsure"


@pytest.mark.parametrize("choice", ["reminder", "goal"])
def test_row7a_row5_created_id_still_links(choice):
    out = _d(
        make(choice, conf=0.3, concern=0.9, explicit=0.9),
        created=TurnCreation(reminder_id="r1"),
    )
    assert (out.kind, out.reason) == ("link", "turn_created")


@pytest.mark.parametrize("choice", ["forget", "ingest", "clarify", "none"])
def test_row9_named_hold_reasons(choice):
    out = _d(make(choice))
    assert (out.kind, out.reason) == ("hold", choice)


@pytest.mark.parametrize("choice", ["forget", "ingest", "clarify", "none", "fact"])
def test_unsure_non_loop_choice_is_choice_unsure(choice):
    out = _d(make(choice, conf=0.4))
    assert (out.kind, out.reason) == ("hold", "choice_unsure")


def test_choice_bar_boundary_is_inclusive():
    assert _d(make("none", conf=0.6)).reason == "none"
    assert _d(make("none", conf=0.5999)).reason == "choice_unsure"


# ── row 8: fact ──────────────────────────────────────────────────────────────


def test_row8_confident_fact_persists_with_family():
    out = _d(make("fact"))
    assert (out.kind, out.reason, out.family) == (
        "persist_fact",
        "persist",
        "preference",
    )
    assert out.consumed == frozenset(
        {"commitment", "resolves_existing", "family", "biography"}
    )


def test_row8_family_drop_holds():
    out = _d(make("fact", family="drop"))
    assert (out.kind, out.reason) == ("hold", "family_drop")


def test_row8_unsure_family_holds():
    assert _d(make("fact", family_conf=0.4)).reason == "family_unsure"


def test_row8_even_biography_holds():
    assert _d(make("fact", bio=0.5)).reason == "not_biography"


def test_row8_biography_boundary_persists():
    assert _d(make("fact", bio=0.7)).kind == "persist_fact"


# ── rows 10-14: loop ─────────────────────────────────────────────────────────


def test_row10_unsure_loop_choice_holds():
    out = _d(make("loop", conf=0.4))
    assert (out.kind, out.reason) == ("hold", "loop_unsure")


def test_row11_not_open_concern_holds():
    out = _d(make("loop", concern=0.4))
    assert (out.kind, out.reason) == ("hold", "not_open_concern")


def test_row11_concern_boundary_creates():
    assert _d(make("loop", concern=0.5, explicit=0.0)).kind == "create_loop_suspected"


def test_row12_tracked_loop_holds():
    out = _d(make("loop"), tracked=True)
    assert (out.kind, out.reason) == ("hold", "tracked")


def test_row13_explicit_creates_declared():
    out = _d(make("loop", explicit=0.8))
    assert (out.kind, out.reason) == ("create_loop_declared", "explicit")
    assert out.consumed == frozenset(
        {"commitment", "resolves_existing", "is_open_concern", "explicit_declaration"}
    )


def test_row14_implied_creates_suspected():
    out = _d(make("loop", explicit=0.79))
    assert (out.kind, out.reason) == ("create_loop_suspected", "implied")


def test_tracked_does_not_block_fact_or_link_side():
    assert _d(make("fact"), tracked=True).kind == "persist_fact"


# ── never raises ─────────────────────────────────────────────────────────────


def test_never_raises_on_garbage():
    result = SystemOneResult(
        outcome="ok", answers={"commitment": object(), "resolves_existing": None}
    )
    assert _d(result).kind == "fallback"
