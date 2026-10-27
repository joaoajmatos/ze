"""Calibration for the skills System One surface (phase 166).

`make calibrate-skills` calls the real System One endpoint over
eval/calibration/skills.jsonl against the fixed roster in skills_roster.yaml. It costs
credits and is never collected by pytest. `--recall` is offline: it needs only the local
E5 model and prints shortlist recall of the gold skill, no System One call.

Per row it builds the production shortlist (`ze_skills.judge.shortlist`, the same helper
the matcher uses) with the local E5 singleton, asks the production questions with the
option order shuffled (eval only), then reports:

- Choice accuracy against the gold skill and a peakedness reliability table;
- `none` precision and recall;
- Noul separation between rows that need a skill and rows that do not;
- a grid of `choice_trust` x `needs_skill_hold` with the wrong-skill applies and the
  missed applies each pair would cause;
- gold recall at k = 3..8 and shortlist floors 0.30..0.45, per language;
- suggested values.

Explicit `/slug` rows bypass the judgment in production, so they are left out of every
metric. History rows are embedded from the raw text only, as the matcher does.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import yaml

from ze_skills.judge import (
    NONE_KEY,
    Q_NEEDS,
    Q_SKILL,
    SkillsSurfaceConfig,
    build_judgment_state_skills,
    build_questions,
    decide,
    shortlist,
    skill_keys,
)
from ze_skills.types import Skill, SkillSource, SkillStatus

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402

DATASET = Path(__file__).with_name("skills.jsonl")
ROSTER = Path(__file__).with_name("skills_roster.yaml")
RECALL_KS = range(3, 9)
RECALL_FLOORS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70, 0.75]
RECALL_TARGET = 0.95
BANDS = {"above", "below_floor", "none"}
LANGS = harness.LANGS


@dataclass
class Row:
    id: str
    lang: str
    text: str
    gold: str
    band: str
    explicit: bool = False
    history: str | None = None


@dataclass
class Outcome:
    row: Row
    keys: list[str]
    result: Any

    @property
    def ok(self) -> bool:
        return self.result.outcome == "ok"


load_rows = harness.row_loader(Row)


def load_roster(path: Path = ROSTER) -> list[Skill]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))["skills"]
    return [
        Skill(
            name=item["name"],
            description=item["description"],
            instructions="(calibration roster)",
            source=SkillSource(item["source"]),
            slug=item["slug"],
            status=SkillStatus.ACTIVE,
            id=uuid5(NAMESPACE_URL, item["slug"]),
        )
        for item in raw
    ]


def score(embedder: Any, skills: list[Skill], text: str) -> list[tuple[Skill, float]]:
    """Cosine of the raw text against each skill's `name: description` passage."""
    matrix = embedder.encode_passage(
        [f"{s.name}: {s.description}" for s in skills], normalize_embeddings=True
    )
    vec = embedder.encode_query(text, normalize_embeddings=True)
    return [(s, float(sim)) for s, sim in zip(skills, (matrix @ vec).tolist())]


def judged(rows: list[Row]) -> list[Row]:
    return [r for r in rows if not r.explicit]


def recall_at(
    scored: dict[str, list[tuple[Skill, float]]],
    rows: list[Row],
    *,
    k: int,
    floor: float,
) -> tuple[int, int]:
    """(hits, total) of gold skill inside the production shortlist, gold rows only."""
    gold_rows = [r for r in judged(rows) if r.gold != NONE_KEY]
    hits = sum(
        r.gold in {s.slug for s, _ in shortlist(scored[r.id], floor=floor, k=k)}
        for r in gold_rows
    )
    return hits, len(gold_rows)


def run_recall(
    embedder: Any, skills: list[Skill], rows: list[Row], *, floor: float, k: int
) -> dict[str, dict[int, float]]:
    scored = {r.id: score(embedder, skills, r.text) for r in rows}
    table: dict[str, dict[int, float]] = {}
    print(f"\n== gold recall by k (shortlist_floor={floor})")
    print("lang   " + "".join(f"k={n:<6d}" for n in RECALL_KS))
    for lang in (*LANGS, "all"):
        scoped = [r for r in rows if lang == "all" or r.lang == lang]
        cells: dict[int, float] = {}
        for n in RECALL_KS:
            hits, total = recall_at(scored, scoped, k=n, floor=floor)
            cells[n] = hits / total if total else 0.0
        table[lang] = cells
        print(f"{lang:<7s}" + "".join(f"{cells[n]:<8.3f}" for n in RECALL_KS))

    print(f"\n== gold recall by shortlist_floor (k={k})")
    print("lang   " + "".join(f"f={f:<6.2f}" for f in RECALL_FLOORS))
    for lang in (*LANGS, "all"):
        scoped = [r for r in rows if lang == "all" or r.lang == lang]
        cells_f = []
        for f in RECALL_FLOORS:
            hits, total = recall_at(scored, scoped, k=k, floor=f)
            cells_f.append(hits / total if total else 0.0)
        print(f"{lang:<7s}" + "".join(f"{v:<8.3f}" for v in cells_f))

    gold_rows = [r for r in judged(rows) if r.gold != NONE_KEY]
    sims = {
        r.id: next(sim for s, sim in scored[r.id] if s.slug == r.gold)
        for r in gold_rows
    }
    for band in ("above", "below_floor"):
        vals = [sims[r.id] for r in gold_rows if r.band == band]
        if vals:
            print(
                f"gold cosine, band {band}: n={len(vals)} mean={statistics.mean(vals):.3f}"
                f" min={min(vals):.3f} max={max(vals):.3f}"
            )
    none_tops = [
        max(sim for _, sim in scored[r.id]) for r in judged(rows) if r.gold == NONE_KEY
    ]
    if none_tops:
        print(
            f"top cosine on no-skill rows: n={len(none_tops)} mean={statistics.mean(none_tops):.3f}"
            f" min={min(none_tops):.3f} max={max(none_tops):.3f}"
        )
    smallest = _smallest_k(table)
    if smallest is not None:
        print(
            f"\nSmallest k reaching recall >= {RECALL_TARGET} in both languages: {smallest}"
        )
    else:
        print(
            f"\nNo k in {RECALL_KS.start}..{RECALL_KS.stop - 1} reaches recall {RECALL_TARGET} in both languages."
        )
    return table


def _smallest_k(table: dict[str, dict[int, float]]) -> int | None:
    for n in RECALL_KS:
        if all(table[lang][n] >= RECALL_TARGET for lang in LANGS):
            return n
    return None


# ── live path ───────────────────────────────────────────────────────────


def prepare(
    embedder: Any,
    skills: list[Skill],
    rows: list[Row],
    *,
    seed: int,
    k: int,
    floor: float,
) -> dict[str, tuple[Row, list[str], dict, dict]]:
    """Per judged row with a shortlist: the row, its option keys, the state and the questions."""
    prepared = {}
    for index, row in enumerate(judged(rows)):
        candidates = shortlist(score(embedder, skills, row.text), floor=floor, k=k)
        if not candidates:
            continue
        order = [s for s, _ in candidates]
        random.Random(seed * 100003 + index).shuffle(order)
        keys = skill_keys(order)
        base = {"user": row.text, **({"history": row.history} if row.history else {})}
        prepared[row.id] = (
            row,
            list(keys),
            build_judgment_state_skills(base, order),
            build_questions(keys),
        )
    return prepared


def predicted(outcome: Outcome) -> tuple[str | None, float | None]:
    answer = outcome.result.answers.get(Q_SKILL)
    if answer is None:
        return None, None
    choice = answer.choice
    if choice and " (" in choice:
        choice = choice.split(" (", 1)[0]
    return choice, answer.confidence


def report_accuracy(outcomes: list[Outcome]) -> None:
    for lang in LANGS:
        scoped = [o for o in outcomes if o.ok and o.row.lang == lang]
        hits = sum(predicted(o)[0] == o.row.gold for o in scoped)
        if scoped:
            print(
                f"\n== [{lang}] Choice accuracy vs gold: {hits}/{len(scoped)} = {hits / len(scoped):.3f}"
            )
        for o in scoped:
            if predicted(o)[0] != o.row.gold:
                print(f"   miss {o.row.id}: gold={o.row.gold} pred={predicted(o)[0]}")


def show_reliability(outcomes: list[Outcome]) -> None:
    points = [
        (conf, choice == o.row.gold)
        for o in outcomes
        if o.ok
        for choice, conf in [predicted(o)]
        if conf is not None
    ]
    harness.print_reliability(
        "Choice peakedness reliability",
        harness.reliability_bins(points),
        "mean_conf",
        "accuracy",
        show_ece=True,
    )


def report_none(outcomes: list[Outcome]) -> None:
    scoped = [o for o in outcomes if o.ok]
    tp = sum(predicted(o)[0] == NONE_KEY and o.row.gold == NONE_KEY for o in scoped)
    fp = sum(predicted(o)[0] == NONE_KEY and o.row.gold != NONE_KEY for o in scoped)
    fn = sum(predicted(o)[0] != NONE_KEY and o.row.gold == NONE_KEY for o in scoped)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    print(
        f"\n== none: precision {precision:.2f} recall {recall:.2f} (tp={tp} fp={fp} fn={fn})"
    )


def noul_values(outcomes: list[Outcome], needs: bool) -> list[float]:
    values = []
    for o in outcomes:
        answer = o.result.answers.get(Q_NEEDS) if o.ok else None
        if (
            answer is not None
            and answer.noul is not None
            and (o.row.gold != NONE_KEY) == needs
        ):
            values.append(answer.noul)
    return values


def report_noul(outcomes: list[Outcome]) -> None:
    print("\n== needs_skill Noul (raw values; confirm the wire scale on the first run)")
    for label, needs in (("needs skill", True), ("no skill", False)):
        values = noul_values(outcomes, needs)
        if values:
            print(
                f"{label:12s} n={len(values):3d} mean={statistics.mean(values):.2f}"
                f" min={min(values):.2f} max={max(values):.2f}"
            )


def grid_metrics(outcomes: list[Outcome]) -> list[dict[str, float]]:
    scored = [o for o in outcomes if o.ok]

    def counts(bars: dict[str, float]) -> dict[str, float]:
        cfg = harness.surface_config(
            SkillsSurfaceConfig, choice_trust=bars["trust"], needs_skill_hold=bars["hold"]
        )
        wrong = missed = correct = 0
        for o in scored:
            decision = decide(o.result, cfg, o.keys)
            key = decision.skill_key.split(" (", 1)[0] if decision.skill_key else None
            if decision.kind == "apply":
                if key == o.row.gold:
                    correct += 1
                else:
                    wrong += 1
            elif o.row.gold != NONE_KEY and decision.kind != "abstain":
                missed += 1
        return {**bars, "wrong": wrong, "missed": missed, "correct": correct}

    grid = harness.bar_grid({"trust": harness.GRID, "hold": harness.GRID}, counts)
    return [m for _, m in grid]


def show_grid(metrics: list[dict[str, float]]) -> tuple[float, float] | None:
    harness.print_grid(
        "wrong/correct/missed applies (choice_trust rows, needs_skill_hold cols)",
        "trust\\hold ".ljust(11),
        [({"trust": m["trust"], "hold": m["hold"]}, m) for m in metrics],
        "trust",
        "hold",
        lambda m: f"{int(m['wrong']):>4d}/{int(m['correct'])}/{int(m['missed']):<4d}",
        width=12,
    )
    safe = [m for m in metrics if m["wrong"] == 0 and m["correct"] > 0]
    if not safe:
        print("\nNo bar pair applies a skill with zero wrong applies on this set.")
        return None
    best = max(safe, key=lambda m: (m["correct"], -(m["trust"] + m["hold"])))
    print(
        f"\nSuggested: choice_trust: {best['trust']}  needs_skill_hold: {best['hold']}"
        f"  ({int(best['correct'])} correct applies, 0 wrong applies)"
    )
    return best["trust"], best["hold"]


def report(outcomes: list[Outcome]) -> dict[str, float | None]:
    report_accuracy(outcomes)
    show_reliability(outcomes)
    report_none(outcomes)
    report_noul(outcomes)
    pair = show_grid(grid_metrics(outcomes))
    return {
        "choice_trust": pair[0] if pair else None,
        "needs_skill_hold": pair[1] if pair else None,
    }


def get_embedder() -> Any:
    from ze_core.embeddings import get_embedder as _get

    return _get()


async def main_async(args: argparse.Namespace, embedder: Any = None) -> int:
    skills = load_roster(args.roster)
    rows = load_rows(args.dataset)
    embedder = embedder or get_embedder()
    if args.recall:
        run_recall(embedder, skills, rows, floor=args.floor, k=args.k)
        return 0

    prepared = prepare(
        embedder, skills, rows, seed=args.seed, k=args.k, floor=args.floor
    )
    results = await harness.collect(
        args,
        [p[0] for p in prepared.values()],
        lambda row: prepared[row.id][2],
        lambda _, row: prepared[row.id][3],
        lambda model: (
            f"model={model} rows={len(rows)} skills={len(skills)} k={args.k}"
            f" floor={args.floor} seed={args.seed}"
        ),
    )
    if results is None:
        return 2
    run_recall(embedder, skills, rows, floor=args.floor, k=args.k)
    outcomes = [Outcome(row, keys, results[row.id]) for row, keys, _, _ in prepared.values()]
    skipped = [o for o in outcomes if not o.ok]
    if skipped:
        print(f"skipped rows (excluded from metrics): {len(skipped)}")
    if not any(o.ok for o in outcomes):
        print("Every call was skipped; nothing to calibrate.", file=sys.stderr)
        return 1
    suggestion = report(outcomes)
    print(
        "\nCopy into apps/ze-api/config/config.yaml under system_one.surfaces.skills,"
        " then enable system_one and the surface:"
    )
    for key, value in suggestion.items():
        print(
            f"  {key}: {value if value is not None else 'null  # no safe value on this set'}"
        )
    return 0


def parser() -> argparse.ArgumentParser:
    cfg = harness.configured(SkillsSurfaceConfig)
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    harness.common_args(p, seed=166, check_sets=False)
    p.add_argument(
        "--recall", action="store_true", help="offline: print shortlist recall only"
    )
    p.add_argument("--dataset", type=Path, default=DATASET)
    p.add_argument("--roster", type=Path, default=ROSTER)
    p.add_argument("--k", type=int, default=cfg.shortlist_k)
    p.add_argument("--floor", type=float, default=cfg.shortlist_floor)
    return p


def main() -> None:
    raise SystemExit(asyncio.run(main_async(parser().parse_args())))


if __name__ == "__main__":
    main()
