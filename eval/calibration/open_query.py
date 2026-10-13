"""Calibration for the language-neutral "what's open" detector (phase 171).

`make calibrate-open-query` runs the local E5 embedder over the labeled EN+PT set
(eval/calibration/open_query.jsonl). It is free: the model files are local and no
OpenRouter or System One call is made. Never collected by pytest.

- `--check-sets`: offline. Dataset shape, unique ids, no cross-file overlap and
  per-language/label counts; exits 1 on any violation. Works before
  `ze_priority.open_query` exists.
- `--set tuned` (default): sweeps thresholds 0.80-0.95 step 0.005 over the tuned
  set and prints per-language recall and false-positive rate, then the lowest
  threshold with tuned FPR <= 0.02 in both languages.
- `--set holdout --threshold T`: the single verdict run on
  eval/calibration/open_query_holdout.jsonl. PASS per language iff recall >= 0.90
  and FPR <= 0.05. Prints the misclassified ids.

The held-out file is written before any tuning and must never be tuned on; if it
fails, fix the examples or threshold on the tuned set and write a new held-out
file before the next verdict (research.md R5).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

LANGS = ("en", "pt")
MIN_TUNED_PER_LANG = 40
MIN_HOLDOUT_PER_LANG = 20
SWEEP_START = 0.80
SWEEP_STOP = 0.95
SWEEP_STEP = 0.005
FPR_TARGET_TUNED = 0.02
HOLDOUT_RECALL_BAR = 0.90
HOLDOUT_FPR_BAR = 0.05

TUNED = Path(__file__).with_name("open_query.jsonl")
HOLDOUT = Path(__file__).with_name("open_query_holdout.jsonl")
HOLDOUT2 = Path(__file__).with_name("open_query_holdout2.jsonl")


@dataclass(frozen=True)
class Row:
    id: str
    lang: str
    text: str
    label: bool


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def load_rows(path: Path) -> list[Row]:
    rows: list[Row] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            raw = json.loads(line)
            rows.append(Row(raw["id"], raw["lang"], raw["text"], bool(raw["label"])))
    return rows


def shape_problems(
    tuned: list[Row], holdout: list[Row], holdout2: list[Row] | None = None
) -> list[str]:
    problems: list[str] = []
    for name, rows, minimum in (
        ("tuned", tuned, MIN_TUNED_PER_LANG),
        ("holdout", holdout, MIN_HOLDOUT_PER_LANG),
    ):
        for lang in LANGS:
            scoped = [r for r in rows if r.lang == lang]
            if len(scoped) < minimum:
                problems.append(f"{name}/{lang}: {len(scoped)} rows, need >= {minimum}")
            for r in scoped:
                if not r.text.strip():
                    problems.append(f"{name}/{r.id}: empty text")
        if len({r.id for r in rows}) != len(rows):
            problems.append(f"{name}: duplicate ids")
        if len({_norm(r.text) for r in rows}) != len(rows):
            problems.append(f"{name}: duplicate text")
    if holdout2:
        for lang in LANGS:
            if len([r for r in holdout2 if r.lang == lang]) < MIN_HOLDOUT_PER_LANG:
                problems.append(f"holdout2/{lang}: too few rows")
        if len({r.id for r in holdout2}) != len(holdout2):
            problems.append("holdout2: duplicate ids")
        seen = {_norm(r.text) for r in tuned + holdout}
        for r in holdout2:
            if _norm(r.text) in seen:
                problems.append(f"holdout2/{r.id}: text shared with another set")
        if {r.id for r in holdout2} & {r.id for r in tuned + holdout}:
            problems.append("ids repeat across holdout2 and other sets")
    ids = [r.id for r in tuned + holdout]
    if len(ids) != len(set(ids)):
        problems.append("ids repeat across tuned and holdout")
    held = {_norm(r.text) for r in holdout}
    for r in tuned:
        if _norm(r.text) in held:
            problems.append(f"tuned/{r.id}: text equals a held-out text")
    for r in tuned + holdout:
        if r.lang not in LANGS:
            problems.append(f"{r.id}: bad lang {r.lang!r}")
    return problems


def check_sets() -> int:
    tuned, holdout = load_rows(TUNED), load_rows(HOLDOUT)
    holdout2 = load_rows(HOLDOUT2) if HOLDOUT2.exists() else None
    named = [("tuned", tuned), ("holdout", holdout)]
    if holdout2:
        named.append(("holdout2", holdout2))
    for name, rows in named:
        counts = Counter((r.lang, r.label) for r in rows)
        print(f"{name}: {len(rows)} rows")
        for lang in LANGS:
            pos = counts[(lang, True)]
            neg = counts[(lang, False)]
            print(f"  {lang}: {pos + neg} rows, {pos} positive, {neg} negative")
    problems = shape_problems(tuned, holdout, holdout2)
    for problem in problems:
        print("PROBLEM:", problem, file=sys.stderr)
    return 1 if problems else 0


def threshold_grid() -> list[float]:
    count = int(round((SWEEP_STOP - SWEEP_START) / SWEEP_STEP))
    return [round(SWEEP_START + SWEEP_STEP * i, 3) for i in range(count + 1)]


def similarities(rows: list[Row]) -> dict[str, float]:
    from ze_core.embeddings import get_embedder
    from ze_priority.open_query import OpenQueryDetector

    embedder = get_embedder()
    detector = OpenQueryDetector(embedder, threshold=0.0)
    embeddings = embedder.encode([r.text for r in rows], normalize_embeddings=True)
    return {
        r.id: detector.best_similarity(vec) for r, vec in zip(rows, embeddings)
    }


def _recall_fpr(rows: list[Row], sims: dict[str, float], threshold: float) -> tuple[float, float]:
    pos = [r for r in rows if r.label]
    neg = [r for r in rows if not r.label]
    hit = sum(sims[r.id] >= threshold for r in pos)
    false = sum(sims[r.id] >= threshold for r in neg)
    recall = hit / len(pos) if pos else 0.0
    fpr = false / len(neg) if neg else 0.0
    return recall, fpr


def report_tuned(rows: list[Row], sims: dict[str, float]) -> int:
    grid = threshold_grid()
    print("\n== tuned sweep (recall / FPR per language)")
    print("threshold   " + "".join(f"{lang:>18s}" for lang in LANGS))
    suggested: float | None = None
    for threshold in grid:
        cells = ""
        for lang in LANGS:
            scoped = [r for r in rows if r.lang == lang]
            recall, fpr = _recall_fpr(scoped, sims, threshold)
            cells += f"  {recall:.3f}/{fpr:.3f}     "
        print(f"{threshold:>7.3f}   {cells}")
        if suggested is None:
            ok = all(
                _recall_fpr([r for r in rows if r.lang == lang], sims, threshold)[1]
                <= FPR_TARGET_TUNED
                for lang in LANGS
            )
            if ok:
                suggested = threshold
    print(
        "\nSuggested threshold (lowest with tuned FPR <= "
        f"{FPR_TARGET_TUNED} in both languages): "
        f"{suggested if suggested is not None else 'none on this grid'}"
    )
    return 0


def report_holdout(rows: list[Row], sims: dict[str, float], threshold: float) -> int:
    print(f"\n== HELD-OUT VERDICT (threshold {threshold:.3f})")
    passed = True
    for lang in LANGS:
        scoped = [r for r in rows if r.lang == lang]
        recall, fpr = _recall_fpr(scoped, sims, threshold)
        ok = recall >= HOLDOUT_RECALL_BAR and fpr <= HOLDOUT_FPR_BAR
        passed &= ok
        print(
            f"[{lang}] {'PASS' if ok else 'FAIL'}"
            f"  recall {recall:.3f} (>= {HOLDOUT_RECALL_BAR})"
            f"  FPR {fpr:.3f} (<= {HOLDOUT_FPR_BAR})"
        )
        for r in scoped:
            predicted = sims[r.id] >= threshold
            if predicted != r.label:
                kind = "false positive" if predicted else "false negative"
                print(f"    {kind}: {r.id} sim={sims[r.id]:.3f}  {r.text}")
    print(f"OVERALL: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check-sets", action="store_true", help="offline dataset shape check")
    parser.add_argument("--set", choices=("tuned", "holdout", "holdout2"), default="tuned")
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="detector threshold; required for --set holdout",
    )
    args = parser.parse_args()

    if args.check_sets:
        return check_sets()

    problems = shape_problems(
        load_rows(TUNED),
        load_rows(HOLDOUT),
        load_rows(HOLDOUT2) if HOLDOUT2.exists() else None,
    )
    if problems:
        print("Dataset problems; run --check-sets.", file=sys.stderr)
        return 1

    if args.set != "tuned" and args.threshold is None:
        print("--set holdout/holdout2 needs --threshold T.", file=sys.stderr)
        return 2

    rows = load_rows({"tuned": TUNED, "holdout": HOLDOUT, "holdout2": HOLDOUT2}[args.set])
    try:
        sims = similarities(rows)
    except ImportError as exc:
        print(
            f"cannot import the detector ({exc}); land T029 (ze_priority.open_query) first.",
            file=sys.stderr,
        )
        return 2

    if args.set != "tuned":
        return report_holdout(rows, sims, args.threshold)
    return report_tuned(rows, sims)


if __name__ == "__main__":
    raise SystemExit(main())
