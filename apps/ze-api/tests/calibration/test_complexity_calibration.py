"""Pure scoring, verdict and offline --check-sets of eval/calibration/complexity.py (phase 182).

Fakes and synthetic rows only. No network, no credits, and no read of the held-out file.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[4] / "eval/calibration/complexity.py"
_LEAK = "ZEBRA-PROMPT-7731"


@pytest.fixture(scope="module")
def calib():
    spec = importlib.util.spec_from_file_location("complexity_calibration", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


def _out(calib, lang: str, tier: str, noul, i: int = 0):
    return calib.Outcome(
        id=f"{lang}-{tier}-{i}",
        lang=lang,
        agent="companion",
        gold_tier=tier,
        noul=noul,
    )


def _clean_lang(calib, lang: str, light: int = 10, full: int = 10):
    """A language that passes every clause at bar 0.35."""
    return [_out(calib, lang, "simple", 0.1, i) for i in range(light)] + [
        _out(calib, lang, "full", 0.9, i) for i in range(full)
    ]


# --- suggest_simple_max (amended FR-017) ---------------------------------------------


def test_bar_keeps_a_margin_of_at_least_0_15_under_the_lowest_full_row(calib):
    outcomes = [
        _out(calib, "en", "simple", 0.02, 0),
        _out(calib, "en", "simple", 0.08, 1),
        _out(calib, "en", "full", 0.56, 2),
        _out(calib, "en", "full", 0.9, 3),
    ]
    assert calib.suggest_simple_max(outcomes) == 0.40


def test_margin_may_be_exactly_0_15(calib):
    outcomes = [
        _out(calib, "en", "simple", 0.1, 0),
        _out(calib, "en", "full", 0.55, 1),
        _out(calib, "en", "full", 0.9, 2),
    ]
    assert calib.suggest_simple_max(outcomes) == 0.40


def test_bar_is_rounded_down_to_a_0_05_step(calib):
    outcomes = [
        _out(calib, "en", "simple", 0.05, 0),
        _out(calib, "en", "full", 0.52, 1),
    ]
    assert calib.suggest_simple_max(outcomes) == 0.35


def test_each_language_needs_tuned_recall_of_at_least_0_8(calib):
    en = [_out(calib, "en", "simple", 0.1, i) for i in range(5)]
    pt = [_out(calib, "pt", "simple", 0.1, i) for i in range(4)] + [
        _out(calib, "pt", "simple", 0.9, 9)
    ]
    full = [_out(calib, "en", "full", 0.7, 20), _out(calib, "pt", "full", 0.7, 21)]
    assert calib.suggest_simple_max(en + pt + full) == 0.55
    pt_low = [_out(calib, "pt", "simple", 0.1, i) for i in range(3)] + [
        _out(calib, "pt", "simple", 0.9, i) for i in (8, 9)
    ]
    assert calib.suggest_simple_max(en + pt_low + full) is None


def test_skipped_simple_rows_count_as_missed_light_rows(calib):
    outcomes = [_out(calib, "en", "simple", 0.1, i) for i in range(3)] + [
        _out(calib, "en", "simple", None, 8),
        _out(calib, "en", "simple", None, 9),
        _out(calib, "en", "full", 0.8, 20),
    ]
    assert calib.suggest_simple_max(outcomes) is None


def test_overlapping_set_has_no_safe_bar(calib):
    outcomes = [
        _out(calib, "en", "simple", 0.4, 0),
        _out(calib, "en", "full", 0.3, 1),
    ]
    assert calib.suggest_simple_max(outcomes) is None


def test_lowest_full_row_too_low_for_the_margin_has_no_bar(calib):
    outcomes = [
        _out(calib, "en", "simple", 0.01, 0),
        _out(calib, "en", "full", 0.10, 1),
    ]
    assert calib.suggest_simple_max(outcomes) is None


def test_no_full_rows_has_no_bar(calib):
    outcomes = [_out(calib, "en", "simple", 0.1, 0)]
    assert calib.suggest_simple_max(outcomes) is None


def test_skipped_full_rows_do_not_bound_the_bar(calib):
    outcomes = [
        _out(calib, "en", "simple", 0.1, 0),
        _out(calib, "en", "full", None, 1),
    ]
    assert calib.suggest_simple_max(outcomes) is None


# --- verdict -------------------------------------------------------------------------


def test_one_false_downgrade_keeps_only_that_language_off(calib):
    outcomes = _clean_lang(calib, "en") + _clean_lang(calib, "pt")
    outcomes.append(_out(calib, "pt", "full", 0.1, 99))

    v = calib.verdict(outcomes, 0.35)

    assert v.per_lang["pt"].false_downgrades == 1
    assert v.per_lang["pt"].enabled is False
    assert v.per_lang["en"].enabled is True
    assert v.enabled is False


def test_recall_below_half_fails_the_language(calib):
    outcomes = [_out(calib, "en", "simple", 0.1, i) for i in range(49)]
    outcomes += [_out(calib, "en", "simple", 0.9, 100 + i) for i in range(51)]

    lang = calib.verdict(outcomes, 0.35).per_lang["en"]

    assert lang.recall == pytest.approx(0.49)
    assert lang.enabled is False
    assert any(line.startswith("light recall") for line in lang.failing)


def test_recall_of_exactly_half_passes(calib):
    outcomes = [_out(calib, "en", "simple", 0.1, i) for i in range(50)]
    outcomes += [_out(calib, "en", "simple", 0.9, 100 + i) for i in range(50)]

    lang = calib.verdict(outcomes, 0.35).per_lang["en"]

    assert lang.recall == pytest.approx(0.5)
    assert lang.enabled is True


def test_eleven_percent_skipped_fails(calib):
    outcomes = [_out(calib, "en", "simple", 0.1, i) for i in range(89)]
    outcomes += [_out(calib, "en", "full", None, 100 + i) for i in range(11)]

    lang = calib.verdict(outcomes, 0.35).per_lang["en"]

    assert lang.skipped == 11
    assert lang.enabled is False
    assert any(line.startswith("skipped") for line in lang.failing)


def test_ten_percent_skipped_passes(calib):
    outcomes = [_out(calib, "en", "simple", 0.1, i) for i in range(90)]
    outcomes += [_out(calib, "en", "full", None, 100 + i) for i in range(10)]

    lang = calib.verdict(outcomes, 0.35).per_lang["en"]

    assert lang.skipped_share == pytest.approx(0.10)
    assert lang.enabled is True


def test_every_clause_passing_in_both_languages_enables_overall(calib):
    outcomes = _clean_lang(calib, "en") + _clean_lang(calib, "pt")

    v = calib.verdict(outcomes, 0.35)

    assert v.per_lang["en"].enabled is True
    assert v.per_lang["pt"].enabled is True
    assert v.enabled is True


def test_noul_equal_to_simple_max_counts_as_light(calib):
    outcomes = [_out(calib, "en", "simple", 0.35, 0), _out(calib, "en", "full", 0.9, 1)]

    lang = calib.verdict(outcomes, 0.35).per_lang["en"]

    assert lang.true_light == 1
    assert lang.recall == pytest.approx(1.0)
    assert lang.false_downgrades == 0


# --- --check-sets -------------------------------------------------------------------


def _row(calib, **over):
    fields = dict(
        id="r",
        lang="en",
        agent="companion",
        conversation=[],
        recap=None,
        memory=[],
        focus=None,
        skill=None,
        prompt="a plain prompt",
        gold_tier="simple",
        kind=["single"],
    )
    fields.update(over)
    return calib.Row(**fields)


ANAPHORA = {"role": "user", "content": "an earlier turn"}


def test_missing_anaphoric_quota_is_flagged_without_row_text(calib):
    quota = calib.Quota(
        rows=0,
        per_tier=0,
        per_agent_tier=0,
        conversation=0,
        anaphoric=6,
        anaphoric_per_tier=0,
        per_context=0,
        single=0,
    )
    rows = [
        _row(
            calib,
            id=f"a{i}",
            lang="en",
            conversation=[ANAPHORA],
            prompt=f"{_LEAK} what about it",
            kind=["anaphoric"],
        )
        for i in range(3)
    ]

    problems = calib.shape_problems(rows, "unit", quota)

    assert "unit/en: 3 anaphoric rows, need >= 6" in problems
    assert all(_LEAK not in p for p in problems)


def test_schema_problems_name_the_row_without_its_text(calib):
    quota = calib.Quota(0, 0, 0, 0, 0, 0, 0, 0)
    bad = _row(calib, id="bad-1", gold_tier="bogus", prompt=f"{_LEAK} text")

    problems = calib.shape_problems([bad], "unit", quota)

    assert any("unit/bad-1: bad gold_tier" in p for p in problems)
    assert all(_LEAK not in p for p in problems)


def test_cross_set_duplicate_prompt_is_flagged_without_its_text(calib):
    tuned = [_row(calib, id="t1", prompt=f"  {_LEAK.lower()}  ")]
    holdout = [_row(calib, id="h1", prompt=_LEAK)]

    problems = calib.cross_problems(tuned, holdout)

    assert problems == ["tuned/t1: prompt equals a held-out prompt"]
    assert all(_LEAK.lower() not in p.lower() for p in problems)


# Shape-valid fixtures. Each row carries only the features its tags declare, so the
# quotas in TUNED_QUOTA and HOLDOUT_QUOTA are met exactly per language.
def _shaped_rows(
    calib,
    prefix: str,
    n: int,
    *,
    simple_upto: int,
    conv_upto: int,
    anaphoric: set[int],
    memory: set[int],
    focus: set[int],
    skill: set[int],
    recap: set[int],
    single: set[int],
) -> list:
    rows = []
    for lang in calib.LANGS:
        for i in range(n):
            tier = "simple" if i < simple_upto else "full"
            kind = []
            if i in single:
                kind.append("single")
            if i in anaphoric:
                kind.append("anaphoric")
            rows.append(
                _row(
                    calib,
                    id=f"{prefix}-{lang}-{i:02d}",
                    lang=lang,
                    agent=calib.AGENTS[i % len(calib.AGENTS)],
                    conversation=[ANAPHORA] if i < conv_upto or i in anaphoric else [],
                    memory=["a remembered fact"] if i in memory else [],
                    focus="a focus" if i in focus else None,
                    skill={"name": "s"} if i in skill else None,
                    recap="a recap" if i in recap else None,
                    prompt=f"{prefix} {lang} prompt {i}",
                    gold_tier=tier,
                    kind=kind,
                )
            )
    return rows


def _tuned_rows(calib):
    return _shaped_rows(
        calib,
        "tuned",
        40,
        simple_upto=20,
        conv_upto=23,
        anaphoric={0, 1, 2, 20, 21, 22},
        memory={23, 24, 25, 26},
        focus={27, 28},
        skill={29, 30},
        recap={31, 32},
        single={36, 37, 38, 39},
    )


def _holdout_rows(calib):
    return _shaped_rows(
        calib,
        "holdout",
        24,
        simple_upto=12,
        conv_upto=15,
        anaphoric={0, 1, 2, 12, 13, 14},
        memory={3, 4, 5, 6},
        focus={7, 8},
        skill={9, 10},
        recap={15, 16},
        single={20, 21, 22, 23},
    )


def _write(path: Path, rows) -> Path:
    path.write_text(
        "\n".join(json.dumps(dataclasses.asdict(r), ensure_ascii=False) for r in rows)
        + "\n",
        encoding="utf-8",
    )
    return path


def test_shaped_fixtures_meet_the_real_quotas(calib):
    assert calib.shape_problems(_tuned_rows(calib), "tuned", calib.TUNED_QUOTA) == []
    assert (
        calib.shape_problems(_holdout_rows(calib), "holdout", calib.HOLDOUT_QUOTA) == []
    )


def test_check_sets_returns_one_for_a_missing_quota(
    calib, monkeypatch, tmp_path, capsys
):
    tuned_rows = _tuned_rows(calib)
    for r in tuned_rows[:4]:
        r.kind = [k for k in r.kind if k != "anaphoric"]
    monkeypatch.setattr(calib, "TUNED", _write(tmp_path / "tuned.jsonl", tuned_rows))
    monkeypatch.setattr(
        calib, "HOLDOUT", _write(tmp_path / "holdout.jsonl", _holdout_rows(calib))
    )

    assert calib.check_sets() == 1
    err = capsys.readouterr().err
    assert "anaphoric rows, need >= 6" in err
    assert _LEAK not in err


def test_check_sets_returns_zero_for_valid_sets(calib, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        calib, "TUNED", _write(tmp_path / "tuned.jsonl", _tuned_rows(calib))
    )
    monkeypatch.setattr(
        calib, "HOLDOUT", _write(tmp_path / "holdout.jsonl", _holdout_rows(calib))
    )

    assert calib.check_sets() == 0
    assert "PROBLEM" not in capsys.readouterr().err


# --- infrastructure failures must not spend the held-out set -------------------------


def _skipped(calib, reason, i):
    return calib.Outcome(
        id=f"s{i}",
        lang="en",
        agent="companion",
        gold_tier="simple",
        noul=None,
        skip_reason=reason,
    )


def test_more_than_half_infrastructure_skips_is_an_infrastructure_failure(calib):
    rows = [_skipped(calib, "timeout", i) for i in range(6)] + [
        _out(calib, "en", "simple", 0.1, i) for i in range(4)
    ]
    assert calib.infrastructure_failure(rows) is True


def test_exactly_half_is_not_an_infrastructure_failure(calib):
    rows = [_skipped(calib, "overload", i) for i in range(5)] + [
        _out(calib, "en", "simple", 0.1, i) for i in range(5)
    ]
    assert calib.infrastructure_failure(rows) is False


def test_invalid_answers_are_the_models_fault_not_infrastructure(calib):
    rows = [_skipped(calib, "invalid_answer", i) for i in range(9)] + [
        _out(calib, "en", "simple", 0.1, 0)
    ]
    assert calib.infrastructure_failure(rows) is False


@pytest.mark.parametrize("reason", ["timeout", "overload", "error", "missing_key"])
def test_each_transport_reason_counts(calib, reason):
    rows = [_skipped(calib, reason, i) for i in range(3)] + [
        _out(calib, "en", "simple", 0.1, 0)
    ]
    assert calib.infrastructure_failure(rows) is True


def _holdout_args(calib, **over):
    import argparse

    base = dict(
        check_sets=False,
        set="holdout",
        simple_max=0.40,
        model=None,
        timeout_ms=None,
        concurrency=2,
        rerun=False,
        without=[],
    )
    base.update(over)
    return argparse.Namespace(**base)


def _prepare_holdout(calib, monkeypatch, tmp_path, answer_for):
    from ze_agents.system_one import SystemOneAnswer, SystemOneResult

    rows = _holdout_rows(calib)
    monkeypatch.setattr(
        calib, "TUNED", _write(tmp_path / "tuned.jsonl", _tuned_rows(calib))
    )
    monkeypatch.setattr(calib, "HOLDOUT", _write(tmp_path / "holdout.jsonl", rows))
    monkeypatch.setattr(calib, "VERDICT_MARKER", tmp_path / "results" / "marker.json")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")

    async def fake_run(client, rows_, concurrency, without=()):
        out = {}
        for r in rows_:
            value = answer_for(r)
            if value is None:
                out[r.id] = SystemOneResult(outcome="skip", skip_reason="timeout")
            else:
                out[r.id] = SystemOneResult(
                    outcome="ok",
                    answers={calib.Q_DEEP: SystemOneAnswer(type="noul", noul=value)},
                    latency_ms=500,
                )
        return out

    monkeypatch.setattr(calib, "run_system_one", fake_run)
    return rows


async def test_a_valid_holdout_run_writes_the_marker_and_cannot_be_repeated(
    calib, monkeypatch, tmp_path, capsys
):
    _prepare_holdout(
        calib, monkeypatch, tmp_path, lambda r: 0.1 if r.gold_tier == "simple" else 0.9
    )
    assert await calib.main_async(_holdout_args(calib)) == 0
    out = capsys.readouterr().out
    assert "OVERALL: ENABLE" in out
    assert calib.VERDICT_MARKER.exists()

    assert await calib.main_async(_holdout_args(calib)) == 2
    assert await calib.main_async(_holdout_args(calib, rerun=True)) == 0


async def test_an_infrastructure_failure_does_not_spend_the_holdout_set(
    calib, monkeypatch, tmp_path, capsys
):
    _prepare_holdout(calib, monkeypatch, tmp_path, lambda r: None)
    assert await calib.main_async(_holdout_args(calib)) == 3
    captured = capsys.readouterr()
    assert "INFRASTRUCTURE FAILURE" in captured.out
    assert "KEEP OFF" not in captured.out
    assert not calib.VERDICT_MARKER.exists()

    _prepare_holdout(
        calib, monkeypatch, tmp_path, lambda r: 0.1 if r.gold_tier == "simple" else 0.9
    )
    assert await calib.main_async(_holdout_args(calib)) == 0


async def test_a_failing_verdict_still_spends_the_set(
    calib, monkeypatch, tmp_path, capsys
):
    _prepare_holdout(calib, monkeypatch, tmp_path, lambda r: 0.1)
    assert await calib.main_async(_holdout_args(calib)) == 0
    assert "OVERALL: KEEP OFF" in capsys.readouterr().out
    assert calib.VERDICT_MARKER.exists()
