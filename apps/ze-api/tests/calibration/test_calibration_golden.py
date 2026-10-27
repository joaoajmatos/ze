"""Every calibration runner prints the same report as the captured golden file. No network.

The runners run in-process against the replay fakes (see ``capture_golden``). The tests are
synchronous because the runners start their own event loop.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest
from tests.calibration.capture_golden import CALIBRATION, MODES, run_mode, run_runner

RUNNERS = list(dict.fromkeys(m.runner for m in MODES))


@pytest.mark.parametrize("runner", RUNNERS)
def test_runner_reproduces_its_golden_files(runner):
    outputs = run_runner(runner)
    modes = {m.name: m for m in MODES if m.runner == runner}
    assert set(outputs) == set(modes)
    for name, text in outputs.items():
        golden = modes[name].golden.read_text(encoding="utf-8")
        assert text == golden, f"{runner} {name} differs from {modes[name].golden.name}"


_BANNER = re.compile(r"^(model=|results loaded from |live run took ).*\n", re.MULTILINE)
RELOADABLE = [
    m
    for m in MODES
    if m.name in ("live", "tuned", "holdout") and m.runner != "commitment_intake"
]


@pytest.mark.parametrize("mode", RELOADABLE, ids=lambda m: f"{m.runner}-{m.name}")
def test_saved_results_reload_to_the_same_report(mode):
    with tempfile.TemporaryDirectory(prefix="calibration-reload-") as raw:
        tmp = Path(raw)
        saved = replace(mode, argv=(*mode.argv, "--save", "{tmp}/saved.json"))
        loaded = replace(mode, argv=(*mode.argv, "--load", "{tmp}/saved.json"))
        first = run_mode(saved, tmp)
        again = run_mode(loaded, tmp)
    assert _BANNER.sub("", again) == _BANNER.sub("", first)
    assert _BANNER.sub("", first) == _BANNER.sub("", mode.golden.read_text(encoding="utf-8"))


_HARNESS_ONLY = (
    "load_rows|_norm|report_reliability|report_grid|save_results|load_results|parse_bars"
    "|config_model|system_one_config|config_system_one"
)


def test_runners_hold_no_copy_of_a_harness_helper():
    definition = re.compile(rf"^\s*(async\s+)?def ({_HARNESS_ONLY})\b", re.MULTILINE)
    direct = re.compile(r"\b\w+SurfaceConfig\(")
    for path in sorted(CALIBRATION.glob("*.py")):
        if path.name == "harness.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert not definition.search(text), f"{path.name} defines a harness helper"
        assert not direct.search(text), f"{path.name} builds a surface config directly"
