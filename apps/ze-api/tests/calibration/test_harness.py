"""eval/calibration/harness.py: the shared calibration plumbing. No network."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_worldstate.loop_judge import LoopGateSurfaceConfig

_SCRIPT = Path(__file__).resolve().parents[4] / "eval/calibration/harness.py"


@pytest.fixture(scope="module")
def harness():
    spec = importlib.util.spec_from_file_location("calibration_harness", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


@dataclass
class _Row:
    id: str
    text: str = ""


def test_load_jsonl_rejects_duplicate_ids(harness, tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text('{"id": "a"}\n{"id": "b"}\n', encoding="utf-8")
    assert [r.id for r in harness.load_jsonl(path, lambda raw: _Row(raw["id"]))] == [
        "a",
        "b",
    ]
    path.write_text('{"id": "a"}\n\n{"id": "a"}\n', encoding="utf-8")
    with pytest.raises(SystemExit, match="duplicate ids"):
        harness.load_jsonl(path, lambda raw: _Row(raw["id"]))


def test_row_loader_fills_missing_fields_from_defaults(harness, tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text('{"id": "a", "extra": 1}\n', encoding="utf-8")
    assert harness.row_loader(_Row)(path) == [_Row("a", "")]


def test_surface_config_is_the_production_parse(harness):
    cfg = harness.surface_config(
        LoopGateSurfaceConfig, loop_hold=0.9, resolves_hold=0.9
    )
    settings = {
        "system_one": {
            "surfaces": {
                "loop_gate": {"enabled": True, "loop_hold": 0.9, "resolves_hold": 0.9}
            }
        }
    }
    assert cfg.calibrated
    assert cfg == LoopGateSurfaceConfig.from_settings(settings)
    assert not harness.surface_config(LoopGateSurfaceConfig, loop_hold=0.9).calibrated
    assert not harness.surface_config(
        LoopGateSurfaceConfig, loop_hold=1.5, resolves_hold=0.9
    ).calibrated


def test_bars_config_rejects_a_bad_bar_list(harness):
    names = ("loop_hold", "resolves_hold")
    assert harness.bars_config(LoopGateSurfaceConfig, "0.7,0.8", names).loop_hold == 0.7
    for text in ("0.7", "0.7,x", "0.7,1.5"):
        with pytest.raises(SystemExit):
            harness.bars_config(LoopGateSurfaceConfig, text, names)


def _results():
    choice = SystemOneAnswer(
        type="choice", choice="loop", confidence=0.8, probabilities={"loop": 0.8, "none": 0.2}
    )
    noul = SystemOneAnswer(type="noul", noul=0.25)
    return {
        "ok": SystemOneResult(
            outcome="ok", model="m", answers={"c": choice, "n": noul}, latency_ms=12
        ),
        "skip": SystemOneResult(outcome="skip", skip_reason="timeout"),
    }


def test_saved_results_round_trip(harness, tmp_path):
    flat = _results()
    harness.save_results(tmp_path / "flat.json", flat)
    assert harness.load_results(tmp_path / "flat.json") == flat

    nested = {"row-1": flat, "row-2": {"system": flat["ok"]}}
    harness.save_results(tmp_path / "nested.json", nested)
    assert harness.load_results(tmp_path / "nested.json") == nested


def test_reliability_bins_match_hand_values(harness):
    bins = harness.reliability_bins(
        [(0.55, True), (0.58, False), (0.95, True)], [0.0, 0.5, 0.6, 1.0001]
    )
    assert [(b.lo, b.n) for b in bins] == [(0.5, 2), (0.6, 1)]
    assert bins[0].mean == pytest.approx(0.565) and bins[0].rate == 0.5
    assert bins[1].mean == 0.95 and bins[1].rate == 1.0
    assert harness.ece(bins) == pytest.approx((2 * 0.065 + 1 * 0.05) / 3)
    assert harness.ece([]) is None


def test_bar_grid_covers_every_pair(harness):
    grid = harness.bar_grid({"a": [0.5, 0.6], "b": [0.7, 0.8, 0.9]}, lambda b: b["a"] + b["b"])
    assert len(grid) == 6
    assert grid[0] == ({"a": 0.5, "b": 0.7}, pytest.approx(1.2))
    assert grid[-1] == ({"a": 0.6, "b": 0.9}, pytest.approx(1.5))


def test_overlap_and_split_problems_name_the_row(harness):
    tuned = [_Row("t1", "Call  Ana"), _Row("t2", "other")]
    held = [_Row("h1", "call ana")]
    assert harness.split_problems(tuned, held) == ["tuned/t1: text equals a held-out text"]
    assert harness.split_problems(tuned, [_Row("t1", "x")]) == [
        "ids repeat across tuned and holdout"
    ]
