"""Calibration for the corroboration System One surface (phase 172).

`make calibrate-corroboration` calls the real System One endpoint with the `same_concern` Noul
over the tuned set (eval/calibration/corroboration.jsonl) and, side by side, an E5 title-cosine
baseline (cosine(new_title, loop_title) >= 0.75, the matcher's own threshold). It costs credits
and is never collected by pytest.

- Default `--set tuned`: per language and inflow corroborate precision and recall, false
  promotions, a reliability table, a grid over `corroborate_hold` and `promote_hold` (C <= P),
  and suggested bars chosen on the tuned set only. Held-out rows are never read or printed.
- `--set holdout --bars C,P`: the single verdict run on eval/calibration/corroboration_holdout.jsonl
  with frozen wording and bars. ENABLE or KEEP OFF per language, with the failing clause. Tuning
  after this run voids the set (FR-020): write a new held-out file before the next verdict.
- `--check-sets`: offline. Dataset shape only, no network.

Acceptance rule per language (FR-020): zero false promotions, corroborate precision >= 0.9 and
>= E5 precision, corroborate recall >= E5 recall - 0.05.

The E5 baseline cannot simulate the single-entity shortcut in `find_matching_loop` (no graph);
the `same_entity_other` rows stand in for it.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ze_agents.system_one import SystemOneResult
from ze_worldstate.corroboration_judge import (
    Q_SAME,
    QUESTION,
    CorroborationSurfaceConfig,
    build_state,
    decide,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402

TUNED = Path(__file__).with_name("corroboration.jsonl")
HOLDOUT = Path(__file__).with_name("corroboration_holdout.jsonl")
LANGS = harness.LANGS
INFLOWS = ("conversation", "email", "calendar", "ingestion")
KINDS = (
    "same",
    "paraphrase",
    "cross_lingual",
    "same_entity_other",
    "same_topic_other",
    "unrelated",
)
POSITIVE_KINDS = ("same", "paraphrase", "cross_lingual")
HARD_NEGATIVE_KINDS = ("same_entity_other", "same_topic_other")
GRID = harness.GRID
MIN_TUNED_PER_LANG = 40
MIN_HOLDOUT_PER_LANG = 20
MIN_TUNED_PER_INFLOW = 4
MIN_HOLDOUT_PER_INFLOW = 2
E5_THRESHOLD = 0.75
PRECISION_FLOOR = 0.9
RECALL_SLACK = 0.05
COUNTED = ("promote", "corroborate")


@dataclass
class Row:
    id: str
    lang: str
    loop_title: str
    loop_inflow: str
    inflow: str
    text: str
    new_title: str
    gold_same: bool
    kind: str


load_rows = harness.row_loader(Row)


def shape_problems(tuned: list[Row], holdout: list[Row]) -> list[str]:
    problems: list[str] = []
    for name, rows, min_lang, min_inflow in (
        ("tuned", tuned, MIN_TUNED_PER_LANG, MIN_TUNED_PER_INFLOW),
        ("holdout", holdout, MIN_HOLDOUT_PER_LANG, MIN_HOLDOUT_PER_INFLOW),
    ):
        problems += harness.min_rows_problems(name, rows, min_lang)
        for lang in LANGS:
            scoped = [r for r in rows if r.lang == lang]
            for inflow in INFLOWS:
                n = sum(r.inflow == inflow for r in scoped)
                if n < min_inflow:
                    problems.append(
                        f"{name}/{lang}/{inflow}: {n} rows, need >= {min_inflow}"
                    )
            hard = sum(r.kind in HARD_NEGATIVE_KINDS for r in scoped)
            if scoped and hard * 3 < len(scoped):
                problems.append(
                    f"{name}/{lang}: {hard} hard negatives of {len(scoped)}, need >= a third"
                )
            if not any(r.kind == "cross_lingual" for r in scoped):
                problems.append(f"{name}/{lang}: no cross_lingual row")
            if not any(r.gold_same for r in scoped):
                problems.append(f"{name}/{lang}: no positive row")
            if not any(not r.gold_same for r in scoped):
                problems.append(f"{name}/{lang}: no negative row")
        for r in rows:
            if r.lang not in LANGS or r.inflow not in INFLOWS:
                problems.append(f"{name}/{r.id}: bad lang or inflow")
            if r.kind not in KINDS:
                problems.append(f"{name}/{r.id}: unknown kind {r.kind!r}")
            elif r.gold_same != (r.kind in POSITIVE_KINDS):
                problems.append(f"{name}/{r.id}: gold_same disagrees with kind {r.kind}")
    return problems + harness.split_problems(tuned, holdout)


# --- metrics -------------------------------------------------------------------------


@dataclass
class Counts:
    n: int = 0
    fallback: int = 0
    positives: int = 0
    counted: int = 0
    true_counted: int = 0
    false_counted: int = 0
    promoted: int = 0
    false_promotions: int = 0

    @property
    def precision(self) -> float:
        return self.true_counted / self.counted if self.counted else 1.0

    @property
    def recall(self) -> float:
        return self.true_counted / self.positives if self.positives else 0.0


def score(rows: list[Row], kinds: dict[str, str]) -> Counts:
    """A `fallback` row counts as a miss; it is never a false corroboration."""
    c = Counts()
    for r in rows:
        kind = kinds[r.id]
        counted = kind in COUNTED
        c.n += 1
        c.fallback += kind == "fallback"
        c.positives += r.gold_same
        c.counted += counted
        c.true_counted += counted and r.gold_same
        c.false_counted += counted and not r.gold_same
        c.promoted += kind == "promote"
        c.false_promotions += kind == "promote" and not r.gold_same
    return c


def verdict(system: Counts, e5: Counts) -> tuple[bool, list[str]]:
    failing: list[str] = []
    if system.false_promotions:
        failing.append(f"false promotions {system.false_promotions} != 0")
    if system.precision < PRECISION_FLOOR:
        failing.append(f"precision {system.precision:.3f} < {PRECISION_FLOOR}")
    if system.precision < e5.precision:
        failing.append(f"precision {system.precision:.3f} < E5 {e5.precision:.3f}")
    if system.recall < e5.recall - RECALL_SLACK:
        failing.append(
            f"recall {system.recall:.3f} < E5 {e5.recall:.3f} - {RECALL_SLACK}"
        )
    return not failing, failing


def bars_config(corroborate_hold: float, promote_hold: float) -> CorroborationSurfaceConfig:
    return harness.surface_config(
        CorroborationSurfaceConfig,
        corroborate_hold=corroborate_hold,
        promote_hold=promote_hold,
    )


def kinds_for(
    rows: list[Row],
    results: dict[str, SystemOneResult],
    cfg: CorroborationSurfaceConfig,
) -> dict[str, str]:
    return {r.id: decide(results[r.id], cfg).kind for r in rows}


def e5_kinds(rows: list[Row], similarity: dict[str, float]) -> dict[str, str]:
    return {
        r.id: "corroborate" if similarity[r.id] >= E5_THRESHOLD else "not_same"
        for r in rows
    }


def suggest_bars(
    rows: list[Row], results: dict[str, SystemOneResult]
) -> CorroborationSurfaceConfig | None:
    """Research R9: smallest zero-false-promotion `promote_hold`, then the smallest
    precision-feasible `corroborate_hold`, each plus one grid step of margin."""
    promote_hold = None
    for p in GRID:
        cfg = bars_config(p, p)
        if score(rows, kinds_for(rows, results, cfg)).false_promotions == 0:
            promote_hold = p
            break
    if promote_hold is None:
        return None
    corroborate_hold = None
    for c in GRID:
        cfg = bars_config(c, 1.0)
        if score(rows, kinds_for(rows, results, cfg)).precision >= PRECISION_FLOOR:
            corroborate_hold = c
            break
    if corroborate_hold is None:
        return None
    step = GRID[1] - GRID[0]
    promote_hold = round(min(1.0, promote_hold + step), 2)
    corroborate_hold = round(min(promote_hold, corroborate_hold + step), 2)
    return bars_config(corroborate_hold, promote_hold)


# --- live runs -----------------------------------------------------------------------


def e5_similarity(embedder: Any, rows: list[Row]) -> dict[str, float]:
    """`find_matching_loop`'s own measure: cosine over `embedder.encode_passage` of both titles."""
    from ze_memory.consolidation_store import _cosine_similarity

    return {
        r.id: float(
            _cosine_similarity(
                embedder.encode_passage(r.new_title), embedder.encode_passage(r.loop_title)
            )
        )
        for r in rows
    }


# --- reports -------------------------------------------------------------------------


def _fmt(c: Counts) -> str:
    return (
        f"n={c.n} fb={c.fallback} P={c.precision:.3f} R={c.recall:.3f} "
        f"({c.true_counted}/{c.positives}) counted={c.counted} falseC={c.false_counted} "
        f"promoted={c.promoted} falsePromo={c.false_promotions}"
    )


def report_scores(
    rows: list[Row],
    system_kinds: dict[str, str],
    e5: dict[str, str],
    *,
    by_inflow: bool,
) -> dict[str, tuple[Counts, Counts]]:
    out: dict[str, tuple[Counts, Counts]] = {}
    for lang in (*LANGS, "all"):
        scoped = [r for r in rows if lang == "all" or r.lang == lang]
        out[lang] = (score(scoped, system_kinds), score(scoped, e5))
        print(f"\n== [{lang}]")
        print("  system one: " + _fmt(out[lang][0]))
        print("  e5 baseline: " + _fmt(out[lang][1]))
        if by_inflow:
            for inflow in INFLOWS:
                sub = [r for r in scoped if r.inflow == inflow]
                if sub:
                    print(
                        f"  {inflow:<12s} s1: {_fmt(score(sub, system_kinds))}\n"
                        f"  {'':<12s} e5: {_fmt(score(sub, e5))}"
                    )
    return out


def report_reliability(rows: list[Row], results: dict[str, SystemOneResult]) -> None:
    points = [
        (ans.noul, r.gold_same)
        for r in rows
        if results[r.id].outcome == "ok"
        if (ans := results[r.id].answers.get(Q_SAME))
        and ans.noul is not None
        and not math.isnan(ans.noul)
    ]
    harness.print_reliability(
        f"Noul reliability: {Q_SAME} (n={len(points)})",
        harness.reliability_bins(points, harness.NOUL_EDGES),
        "mean_noul",
        "gold_same_rate",
    )


def report_grid(rows: list[Row], results: dict[str, SystemOneResult]) -> None:
    def cell(bars: dict[str, float]) -> Counts:
        return score(rows, kinds_for(rows, results, bars_config(bars["c"], bars["p"])))

    harness.print_grid(
        "bar grid: false promotions / corroborate precision / recall"
        " (promote_hold rows, corroborate_hold cols, C <= P)",
        "P\\C        ",
        harness.bar_grid({"p": GRID, "c": GRID}, cell),
        "p",
        "c",
        lambda c: f"{c.false_promotions:>4d}/{c.precision:.2f}/{c.recall:.2f}",
        width=15,
        label_width=8,
        gap=3,
        skip=lambda p, c: c > p,
    )


def report_errors(
    rows: list[Row], results: dict[str, SystemOneResult], kinds: dict[str, str]
) -> None:
    """Tuned set only: every row the surface gets wrong, with its score."""
    print("\n== tuned-set errors at the bars used (id, kind, gold -> decision, score)")
    for r in rows:
        kind = kinds[r.id]
        counted = kind in COUNTED
        if counted == r.gold_same and not (kind == "promote" and not r.gold_same):
            continue
        ans = results[r.id].answers.get(Q_SAME)
        value = f"{ans.noul:.2f}" if ans is not None and ans.noul is not None else "n/a"
        print(
            f"  {r.id} {r.kind} [{r.inflow}]: gold {'same' if r.gold_same else 'other'}"
            f" -> {kind}  {value}"
        )


# --- main ----------------------------------------------------------------------------


def get_embedder() -> Any:
    from ze_core.embeddings import get_embedder as _get

    return _get()


def check_sets() -> int:
    tuned, holdout = load_rows(TUNED), load_rows(HOLDOUT)
    for name, rows in (("tuned", tuned), ("holdout", holdout)):
        print(f"{name}: {len(rows)} rows")
        for lang in LANGS:
            scoped = [r for r in rows if r.lang == lang]
            pos = sum(r.gold_same for r in scoped)
            hard = sum(r.kind in HARD_NEGATIVE_KINDS for r in scoped)
            by_inflow = Counter(r.inflow for r in scoped)
            print(
                f"  {lang}: {len(scoped)} rows, {pos} positive, {len(scoped) - pos} negative,"
                f" {hard} hard negatives, inflows {dict(by_inflow)}"
            )
    return harness.shape_report(shape_problems(tuned, holdout))


async def main_async(args: argparse.Namespace) -> int:
    if args.check_sets:
        return check_sets()
    holdout = args.set == "holdout"
    rows = load_rows(HOLDOUT if holdout else TUNED)
    if shape_problems(load_rows(TUNED), load_rows(HOLDOUT)):
        print("Dataset problems; run --check-sets.", file=sys.stderr)
        return 1
    if holdout and not args.bars:
        print("--set holdout needs frozen --bars CORROBORATE,PROMOTE.", file=sys.stderr)
        return 2
    if holdout:
        harness.held_out_warning("FR-020")
    results = await harness.collect(
        args,
        rows,
        lambda r: build_state(r.loop_title, r.text, r.inflow),
        lambda _, r: {Q_SAME: QUESTION},
        lambda model: f"model={model} set={args.set} rows={len(rows)}",
    )
    if results is None:
        return 2
    e5 = e5_kinds(rows, e5_similarity(get_embedder(), rows))
    skipped = Counter(r.skip_reason for r in results.values() if r.outcome == "skip")
    if skipped:
        print(f"system one skipped rows (count as misses, never false promotions): {dict(skipped)}")

    if not holdout:
        report_reliability(rows, results)
        report_grid(rows, results)
        suggestion = suggest_bars(rows, results)
        cfg = args.bars_cfg or suggestion
        if cfg is None:
            print("\nNo bar pair reaches zero false promotions and precision >= 0.9 on this set.")
            return 0
        kinds = kinds_for(rows, results, cfg)
        print(f"\nbars used: corroborate_hold={cfg.corroborate_hold} promote_hold={cfg.promote_hold}")
        report_scores(rows, kinds, e5, by_inflow=True)
        report_errors(rows, results, kinds)
        if suggestion:
            print(
                "\nSuggested bars (tuned set only): "
                f"corroborate_hold: {suggestion.corroborate_hold}  promote_hold: {suggestion.promote_hold}"
            )
        return 0

    cfg = args.bars_cfg
    out = report_scores(rows, kinds_for(rows, results, cfg), e5, by_inflow=False)

    def detail(s: Counts, e: Counts) -> str:
        return (
            f"system one: P={s.precision:.3f} R={s.recall:.3f} ({s.true_counted}/{s.positives})"
            f" counted={s.counted} falsePromotions={s.false_promotions} fallback={s.fallback}"
            f" | e5: P={e.precision:.3f} R={e.recall:.3f} ({e.true_counted}/{e.positives})"
            f" counted={e.counted}"
        )

    harness.print_verdict(
        {lang: (*verdict(*out[lang]), detail(*out[lang])) for lang in LANGS},
        lead=[f"bars: corroborate_hold={cfg.corroborate_hold} promote_hold={cfg.promote_hold}"],
    )
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    harness.common_args(
        p, sets=("tuned", "holdout"), bars="CORROBORATE,PROMOTE (required for --set holdout)"
    )
    return p


def main() -> None:
    args = parser().parse_args()
    args.bars_cfg = (
        harness.bars_config(
            CorroborationSurfaceConfig, args.bars, ("corroborate_hold", "promote_hold")
        )
        if args.bars
        else None
    )
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
