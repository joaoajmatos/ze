"""Capture the calibration runners' output against the replay fakes.

``uv run python -m tests.calibration.capture_golden`` (from ``apps/ze-api``) runs every mode in
specs/phases/202-judgment-surface/contracts/calibration-harness.md in-process, with
``ReplayClient``, ``HashEmbedder`` and ``FakeHaiku`` patched in, and writes
``golden/<runner>-<mode>.txt``. ``test_calibration_golden.py`` re-runs the same modes and compares.
Nothing is spent and nothing is written outside a temp directory.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import io
import os
import re
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from unittest import mock

from tests.calibration.replay import FakeHaiku, HashEmbedder, ReplayClient

ROOT = Path(__file__).resolve().parents[4]
CALIBRATION = ROOT / "eval" / "calibration"
GOLDEN = Path(__file__).resolve().parent / "golden"
SIBLINGS = ("harness", "commitment_intake_baseline")
BARS_LOOP_GATE = "0.75,0.8"
BARS_CORROBORATION = "0.6,0.8"
BARS_COMMITMENT = "0.7,0.7,0.55,0.6,0.95,0.8"
_WALL_CLOCK = re.compile(r"live run took [0-9.]+s")
_LOG_LINE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d \[\w+\s*\].*\n", re.MULTILINE)


@dataclass(frozen=True)
class Mode:
    runner: str
    name: str
    argv: tuple[str, ...]

    @property
    def golden(self) -> Path:
        return GOLDEN / f"{self.runner}-{self.name}.txt"


def _modes() -> list[Mode]:
    return [
        Mode("routing", "check-sets", ("--check-sets",)),
        Mode("routing", "recall", ("--recall",)),
        Mode("routing", "live", ()),
        Mode("skills", "recall", ("--recall",)),
        Mode("skills", "live", ()),
        Mode("complexity", "check-sets", ("--check-sets",)),
        Mode("complexity", "tuned", ()),
        Mode(
            "complexity",
            "holdout",
            ("--set", "holdout", "--simple-max", "0.40", "--rerun"),
        ),
        Mode("loop_gate", "check-sets", ("--check-sets",)),
        Mode("loop_gate", "tuned", ()),
        Mode("loop_gate", "holdout", ("--set", "holdout", "--bars", BARS_LOOP_GATE)),
        Mode("corroboration", "check-sets", ("--check-sets",)),
        Mode("corroboration", "tuned", ()),
        Mode(
            "corroboration",
            "holdout",
            ("--set", "holdout", "--bars", BARS_CORROBORATION),
        ),
        Mode("commitment_intake", "check-sets", ("--check-sets",)),
        Mode("commitment_intake", "tuned-save", ("--save", "{tmp}/tuned.json")),
        Mode("commitment_intake", "tuned-replay", ("--replay", "{tmp}/tuned.json")),
        Mode(
            "commitment_intake",
            "holdout3-replay",
            (
                "--set",
                "holdout3",
                "--replay",
                "{tmp}/holdout3.json",
                "--bars",
                BARS_COMMITMENT,
            ),
        ),
        Mode("open_query", "check-sets", ("--check-sets",)),
    ]


MODES = _modes()


def _load(stem: str) -> ModuleType:
    name = f"_calibration_{stem}"
    spec = importlib.util.spec_from_file_location(name, CALIBRATION / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _purge(stem: str) -> None:
    for name in (f"_calibration_{stem}", *SIBLINGS):
        sys.modules.pop(name, None)


def _normalise(text: str, tmp: Path) -> str:
    for form in {str(tmp), str(tmp.resolve())}:
        text = text.replace(form, "<TMP>")
    return _WALL_CLOCK.sub("live run took <T>s", _LOG_LINE.sub("", text))


def _run(module: ModuleType, argv: tuple[str, ...], tmp: Path) -> tuple[str, int]:
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with (
        mock.patch.object(sys, "argv", [module.__file__, *argv]),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ):
        try:
            result = module.main()
            code = result if isinstance(result, int) else 0
        except SystemExit as exc:
            code = (
                exc.code
                if isinstance(exc.code, int)
                else (0 if exc.code is None else 1)
            )
            if isinstance(exc.code, str):
                err.write(exc.code + "\n")
    text = out.getvalue()
    if err.getvalue():
        text += "--- stderr ---\n" + err.getvalue()
    return _normalise(text + f"--- exit {code} ---\n", tmp), code


def _prepare_holdout3(module: ModuleType, tmp: Path) -> None:
    """The spent held-out set refuses a live run: build its results file from the replay client."""
    rows = module.load_rows(module.HOLDOUT3)
    results = asyncio.run(module.run_rows(ReplayClient(), rows, 173, 4))
    saver = getattr(module, "save_results", None) or module.harness.save_results
    saver(tmp / "holdout3.json", results)


@contextlib.contextmanager
def _patched(tmp: Path):
    with (
        mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "replay"}),
        mock.patch(
            "ze_core.openrouter.system_one.OpenRouterSystemOneClient", ReplayClient
        ),
        mock.patch("ze_core.openrouter.client.OpenRouterClient", FakeHaiku),
        mock.patch("ze_core.embeddings.get_embedder", lambda *a, **k: HashEmbedder()),
    ):
        yield


def run_mode(
    mode: Mode, tmp: Path, *, prepare: Callable[[ModuleType], None] | None = None
) -> str:
    """Run one mode; ``tmp`` is shared by the modes of one runner so ``--save`` feeds ``--replay``."""
    with _patched(tmp):
        module = _load(mode.runner)
        try:
            if mode.runner == "complexity":
                module.VERDICT_MARKER = tmp / "complexity_holdout_verdict.json"
            if prepare:
                prepare(module)
            argv = tuple(a.replace("{tmp}", str(tmp)) for a in mode.argv)
            text, _ = _run(module, argv, tmp)
        finally:
            _purge(mode.runner)
    return text


def run_runner(runner: str) -> dict[str, str]:
    """Every mode of one runner, in order, sharing one temp directory."""
    outputs: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="calibration-golden-") as raw:
        tmp = Path(raw)
        for mode in (m for m in MODES if m.runner == runner):
            prepare = (
                (lambda module, tmp=tmp: _prepare_holdout3(module, tmp))
                if mode.name == "holdout3-replay"
                else None
            )
            outputs[mode.name] = run_mode(mode, tmp, prepare=prepare)
    return outputs


def main() -> None:
    GOLDEN.mkdir(exist_ok=True)
    for runner in dict.fromkeys(m.runner for m in MODES):
        for name, text in run_runner(runner).items():
            path = GOLDEN / f"{runner}-{name}.txt"
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
