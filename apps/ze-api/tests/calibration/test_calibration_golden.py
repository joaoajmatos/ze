"""Every calibration runner prints the same report as the captured golden file. No network.

The runners run in-process against the replay fakes (see ``capture_golden``). The tests are
synchronous because the runners start their own event loop.
"""

from __future__ import annotations

import pytest
from tests.calibration.capture_golden import MODES, run_runner

RUNNERS = list(dict.fromkeys(m.runner for m in MODES))


@pytest.mark.parametrize("runner", RUNNERS)
def test_runner_reproduces_its_golden_files(runner):
    outputs = run_runner(runner)
    modes = {m.name: m for m in MODES if m.runner == runner}
    assert set(outputs) == set(modes)
    for name, text in outputs.items():
        golden = modes[name].golden.read_text(encoding="utf-8")
        assert text == golden, f"{runner} {name} differs from {modes[name].golden.name}"
