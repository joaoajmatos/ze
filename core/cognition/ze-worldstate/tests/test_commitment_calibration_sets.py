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
