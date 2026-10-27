import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "eval"
    / "calibration"
    / "commitment_intake.py"
)


@pytest.fixture(scope="module")
def cal():
    spec = importlib.util.spec_from_file_location("commitment_intake_cal", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_shipped_sets_have_valid_shape(cal):
    holdout = cal.load_rows(cal.HOLDOUT)
    tuned = cal.load_rows(cal.TUNED) if cal.TUNED.exists() else None
    assert cal.shape_problems(tuned, holdout) == []


def _row(cal, **over):
    base = dict(
        id="x",
        lang="en",
        text="t",
        assistant="a",
        gold_choice="none",
        gold_explicit=False,
        gold_resolves=False,
        turn_created="none",
        kind="none_question",
    )
    base.update(over)
    return cal.Row(**base)


def test_row_problems_flag_inconsistent_rows(cal):
    rows = [
        _row(cal, id="a", gold_choice="bogus"),
        _row(cal, id="b", gold_explicit=True),
        _row(cal, id="c", gold_choice="fact"),
        _row(
            cal, id="d", turn_created="goal", gold_choice="fact", gold_family="identity"
        ),
        _row(cal, id="e", gold_choice="loop", gold_resolves=True),
    ]
    text = "\n".join(cal.row_problems("t", rows))
    for rid in "abcde":
        assert f"t/{rid}:" in text


def test_missing_labels_and_hard_negatives_are_reported(cal):
    problems = cal.set_problems("holdout", [_row(cal)], 1)
    text = "\n".join(problems)
    assert "no row with choice waiting_on" in text
    assert "no waiting_on row" in text
    assert "no mixed row" in text
    assert "holdout/pt: 0 rows" in text


def test_held_out_text_in_tuned_set_is_rejected(cal):
    holdout = cal.load_rows(cal.HOLDOUT)
    leaked = _row(cal, id="leak", text=holdout[0].text.upper())
    assert any(
        "equals a held-out text" in p for p in cal.shape_problems([leaked], holdout)
    )


def test_repeated_ids_across_sets_are_rejected(cal):
    holdout = cal.load_rows(cal.HOLDOUT)
    clash = _row(cal, id=holdout[0].id, text="something else entirely")
    assert any("ids repeat" in p for p in cal.shape_problems([clash], holdout))


def _depth_rows(cal, lang, facts, loops):
    rows = [
        _row(
            cal,
            id=f"{lang}-f{i}",
            lang=lang,
            gold_choice="fact",
            gold_family="identity",
        )
        for i in range(facts)
    ]
    rows += [
        _row(cal, id=f"{lang}-l{i}", lang=lang, gold_choice="loop")
        for i in range(loops)
    ]
    return rows


def test_shipped_holdout_meets_the_fact_and_loop_minimums(cal):
    assert cal.holdout_depth_problems(cal.load_rows(cal.HOLDOUT)) == []


def test_holdout_below_the_fact_minimum_fails(cal):
    rows = _depth_rows(cal, "en", cal.MIN_HOLDOUT_FACT_PER_LANG - 1, 15) + _depth_rows(
        cal, "pt", 15, 15
    )
    problems = cal.holdout_depth_problems(rows)
    assert problems == [
        f"holdout/en: {cal.MIN_HOLDOUT_FACT_PER_LANG - 1} fact rows, need >= 15"
    ]
    assert any("fact rows" in p for p in cal.shape_problems(None, rows))


def test_holdout_below_the_loop_minimum_fails(cal):
    rows = _depth_rows(cal, "en", 15, 15) + _depth_rows(
        cal, "pt", 15, cal.MIN_HOLDOUT_LOOP_PER_LANG - 1
    )
    problems = cal.holdout_depth_problems(rows)
    assert problems == [
        f"holdout/pt: {cal.MIN_HOLDOUT_LOOP_PER_LANG - 1} gold-loop rows, need >= 15"
    ]
    assert any("gold-loop rows" in p for p in cal.shape_problems(None, rows))


def test_loop_rows_that_the_turn_already_booked_do_not_count_as_gold_loop(cal):
    booked = [
        _row(cal, id=f"b{i}", gold_choice="loop", turn_created="reminder")
        for i in range(20)
    ]
    assert cal.holdout_depth_problems(booked + _depth_rows(cal, "pt", 15, 15))[0] == (
        "holdout/en: 0 fact rows, need >= 15"
    )
    assert any("gold-loop rows" in p for p in cal.holdout_depth_problems(booked))


def test_also_loop_is_only_for_mixed_rows_whose_gold_is_not_loop(cal):
    ok = _row(cal, id="a", kind="mixed", gold_choice="fact", gold_family="identity")
    ok.also_loop = True
    assert cal.row_problems("t", [ok]) == []
    wrong_kind = _row(cal, id="b", gold_choice="fact", gold_family="identity")
    wrong_kind.also_loop = True
    loop_gold = _row(cal, id="c", kind="mixed", gold_choice="loop")
    loop_gold.also_loop = True
    booked = _row(
        cal,
        id="d",
        kind="mixed",
        gold_choice="reminder",
        turn_created="reminder",
    )
    booked.also_loop = True
    text = "\n".join(cal.row_problems("t", [wrong_kind, loop_gold, booked]))
    for rid in "bcd":
        assert f"t/{rid}:" in text


def _blind_rows(cal, prefix="h3"):
    rows = []
    for lang in cal.LANGS:
        n = 0

        def add(choice, **over):
            nonlocal n
            n += 1
            rows.append(
                _row(
                    cal,
                    id=f"{prefix}-{lang}-{n}",
                    lang=lang,
                    text=f"{prefix} {lang} text number {n}",
                    gold_choice=choice,
                    kind="blind",
                    **over,
                )
            )

        for _ in range(15):
            add("fact", gold_family="identity")
        for _ in range(15):
            add("loop")
        for choice in cal.CHOICES:
            if choice not in ("fact", "loop"):
                add(choice)
        add("reminder", turn_created="reminder")
        add("goal", turn_created="goal")
        add("none", gold_resolves=True)
    return rows


def test_a_blind_holdout3_with_its_own_kind_names_passes_the_shape_check(cal):
    holdout = cal.load_rows(cal.HOLDOUT)
    h3 = _blind_rows(cal)
    assert cal.shape_problems(None, holdout, None, h3) == []
    assert cal.kind_notes("holdout3", h3)


def test_holdout3_text_or_ids_shared_with_earlier_sets_are_rejected(cal):
    holdout = cal.load_rows(cal.HOLDOUT)
    tuned = cal.load_rows(cal.TUNED)
    h2 = _blind_rows(cal, prefix="h2")
    h3 = _blind_rows(cal, prefix="h3")
    h3[0].text = holdout[3].text.upper()
    h3[1].text = tuned[3].text
    h3[2].text = h2[4].text
    h3[3].id = holdout[0].id
    text = "\n".join(cal.shape_problems(tuned, holdout, h2, h3))
    for rid in ("h3-en-1", "h3-en-2", "h3-en-3"):
        assert f"holdout3/{rid}: text equals" in text
    assert "ids repeat between holdout3" in text


def test_holdout2_is_checked_against_the_tuned_and_spent_sets_too(cal):
    holdout = cal.load_rows(cal.HOLDOUT)
    h2 = _blind_rows(cal, prefix="h2")
    h2[0].text = holdout[0].text
    assert any(
        "holdout2/h2-en-1: text equals" in p
        for p in cal.shape_problems(None, holdout, h2)
    )


def test_holdout3_below_the_depth_minimums_fails(cal):
    holdout = cal.load_rows(cal.HOLDOUT)
    h3 = [r for r in _blind_rows(cal) if not (r.lang == "pt" and r.gold_fact)]
    problems = cal.shape_problems(None, holdout, None, h3)
    assert any(p.startswith("holdout3/pt:") and "fact rows" in p for p in problems)


async def test_the_spent_sets_cannot_run_live(cal, capsys):
    import argparse

    for name in ("holdout", "holdout2", "holdout3"):
        args = argparse.Namespace(
            check_sets=False,
            set=name,
            load=None,
            bars="0.5,0.5,0.5,0.5,0.5,0.5",
        )
        assert await cal.main_async(args) == 2
        err = capsys.readouterr().err
        assert "spent" in err and "fresh" in err


async def test_replaying_spent_holdout3_needs_the_frozen_bars(cal, capsys, tmp_path):
    import argparse

    args = argparse.Namespace(
        check_sets=False, set="holdout3", load=tmp_path / "r.json", bars=None
    )
    assert await cal.main_async(args) == 2
    assert "--bars" in capsys.readouterr().err
