"""Calibration for the commitment-intake System One surface (phase 173).

`make calibrate-commitment-intake` will call the real System One endpoint over the tuned set
(eval/calibration/commitment_intake.jsonl). It costs credits and is never collected by pytest.

Implemented so far:
- `--check-sets`: offline. Dataset shape only, no network.

The live tuned run, the baseline replay and the held-out verdict (`--set holdout --bars ...`)
arrive with T040/T041.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

TUNED = Path(__file__).with_name("commitment_intake.jsonl")
HOLDOUT = Path(__file__).with_name("commitment_intake_holdout.jsonl")
LANGS = ("en", "pt")
CHOICES = (
    "reminder",
    "loop",
    "goal",
    "waiting_on",
    "fact",
    "forget",
    "ingest",
    "clarify",
    "none",
)
CREATED = ("none", "reminder", "goal")
MIN_TUNED_PER_LANG = 60
MIN_HOLDOUT_PER_LANG = 30
HARD_NEGATIVE_KINDS = (
    "reminder_loop_wording",
    "goal_loop_wording",
    "waiting_on",
    "reminder_not_created",
    "goal_not_created",
    "loop_turn_reminder",
    "loop_turn_goal",
)
MIXED_KIND = "mixed"


@dataclass
class Row:
    id: str
    lang: str
    text: str
    assistant: str
    gold_choice: str
    gold_explicit: bool
    gold_resolves: bool
    turn_created: str
    kind: str
    gold_family: str = ""


def load_rows(path: Path) -> list[Row]:
    rows: list[Row] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            raw = json.loads(line)
            rows.append(
                Row(**{k: raw[k] for k in Row.__dataclass_fields__ if k in raw})
            )
    if len({r.id for r in rows}) != len(rows):
        raise SystemExit(f"duplicate ids in {path.name}")
    return rows


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def row_problems(name: str, rows: list[Row]) -> list[str]:
    problems: list[str] = []
    for r in rows:
        if r.lang not in LANGS:
            problems.append(f"{name}/{r.id}: bad lang {r.lang!r}")
        if r.gold_choice not in CHOICES:
            problems.append(f"{name}/{r.id}: bad gold_choice {r.gold_choice!r}")
        if r.turn_created not in CREATED:
            problems.append(f"{name}/{r.id}: bad turn_created {r.turn_created!r}")
        if r.gold_explicit and r.gold_choice not in ("loop", "reminder", "goal"):
            problems.append(
                f"{name}/{r.id}: gold_explicit needs loop, reminder or goal"
            )
        if r.gold_resolves and r.gold_choice == "loop":
            problems.append(f"{name}/{r.id}: gold_resolves with a loop choice")
        if r.turn_created == "reminder" and r.gold_choice not in ("reminder", "loop"):
            problems.append(f"{name}/{r.id}: reminder created under {r.gold_choice}")
        if r.turn_created == "goal" and r.gold_choice not in ("goal", "loop"):
            problems.append(f"{name}/{r.id}: goal created under {r.gold_choice}")
        if r.gold_choice == "fact" and not r.gold_family:
            problems.append(f"{name}/{r.id}: fact row needs gold_family")
    return problems


def set_problems(name: str, rows: list[Row], minimum: int) -> list[str]:
    problems = row_problems(name, rows)
    for lang in LANGS:
        scoped = [r for r in rows if r.lang == lang]
        if len(scoped) < minimum:
            problems.append(f"{name}/{lang}: {len(scoped)} rows, need >= {minimum}")
        for choice in CHOICES:
            if not any(r.gold_choice == choice for r in scoped):
                problems.append(f"{name}/{lang}: no row with choice {choice}")
        for created in CREATED:
            if not any(r.turn_created == created for r in scoped):
                problems.append(f"{name}/{lang}: no row with turn_created {created}")
        for kind in (*HARD_NEGATIVE_KINDS, MIXED_KIND):
            if not any(r.kind == kind for r in scoped):
                problems.append(f"{name}/{lang}: no {kind} row")
        if not any(r.gold_resolves for r in scoped):
            problems.append(f"{name}/{lang}: no resolves row")
    return problems


def shape_problems(tuned: list[Row] | None, holdout: list[Row]) -> list[str]:
    problems = set_problems("holdout", holdout, MIN_HOLDOUT_PER_LANG)
    if tuned is not None:
        problems += set_problems("tuned", tuned, MIN_TUNED_PER_LANG)
        ids = [r.id for r in tuned + holdout]
        if len(ids) != len(set(ids)):
            problems.append("ids repeat across tuned and holdout")
        held = {_norm(r.text) for r in holdout}
        for r in tuned:
            if _norm(r.text) in held:
                problems.append(f"tuned/{r.id}: text equals a held-out text")
    return problems


def check_sets() -> int:
    holdout = load_rows(HOLDOUT)
    tuned = load_rows(TUNED) if TUNED.exists() else None
    print(f"holdout: {len(holdout)} rows")
    if tuned is None:
        print("tuned: not written yet")
    else:
        print(f"tuned: {len(tuned)} rows")
    problems = shape_problems(tuned, holdout)
    for p in problems:
        print(f"PROBLEM {p}")
    return 1 if problems else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--check-sets", action="store_true", help="offline dataset shape check"
    )
    args = p.parse_args()
    if args.check_sets:
        return check_sets()
    print("Live run not implemented yet; use --check-sets.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
