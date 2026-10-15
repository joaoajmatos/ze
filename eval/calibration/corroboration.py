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
import json
import math
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ze_agents.system_one import SystemOneResult
from ze_worldstate.corroboration_judge import (
    Q_SAME,
    QUESTION,
    CorroborationSurfaceConfig,
    build_state,
    decide,
)

ROOT = Path(__file__).resolve().parents[2]
TUNED = Path(__file__).with_name("corroboration.jsonl")
HOLDOUT = Path(__file__).with_name("corroboration_holdout.jsonl")
CONFIG = ROOT / "apps" / "ze-api" / "config" / "config.yaml"
LANGS = ("en", "pt")
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
GRID = [round(0.5 + 0.05 * i, 2) for i in range(10)]
BINS = [0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0001]
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


def load_rows(path: Path) -> list[Row]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            raw = json.loads(line)
            rows.append(Row(**{k: raw[k] for k in Row.__dataclass_fields__}))
    if len({r.id for r in rows}) != len(rows):
        raise SystemExit(f"duplicate ids in {path.name}")
    return rows


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def shape_problems(tuned: list[Row], holdout: list[Row]) -> list[str]:
    problems: list[str] = []
    for name, rows, min_lang, min_inflow in (
        ("tuned", tuned, MIN_TUNED_PER_LANG, MIN_TUNED_PER_INFLOW),
        ("holdout", holdout, MIN_HOLDOUT_PER_LANG, MIN_HOLDOUT_PER_INFLOW),
    ):
        for lang in LANGS:
            scoped = [r for r in rows if r.lang == lang]
            if len(scoped) < min_lang:
                problems.append(f"{name}/{lang}: {len(scoped)} rows, need >= {min_lang}")
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
    ids = [r.id for r in tuned + holdout]
    if len(ids) != len(set(ids)):
        problems.append("ids repeat across tuned and holdout")
    held = {_norm(r.text) for r in holdout}
    for r in tuned:
        if _norm(r.text) in held:
            problems.append(f"tuned/{r.id}: text equals a held-out text")
    return problems


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
        cfg = CorroborationSurfaceConfig(True, p, p)
        if score(rows, kinds_for(rows, results, cfg)).false_promotions == 0:
            promote_hold = p
            break
    if promote_hold is None:
        return None
    corroborate_hold = None
    for c in GRID:
        cfg = CorroborationSurfaceConfig(True, c, 1.0)
        if score(rows, kinds_for(rows, results, cfg)).precision >= PRECISION_FLOOR:
            corroborate_hold = c
            break
    if corroborate_hold is None:
        return None
    step = GRID[1] - GRID[0]
    promote_hold = round(min(1.0, promote_hold + step), 2)
    corroborate_hold = round(min(promote_hold, corroborate_hold + step), 2)
    return CorroborationSurfaceConfig(True, corroborate_hold, promote_hold)


# --- live runs -----------------------------------------------------------------------


async def run_system_one(
    client: Any, rows: list[Row], concurrency: int
) -> dict[str, SystemOneResult]:
    sem = asyncio.Semaphore(concurrency)

    async def one(row: Row) -> tuple[str, SystemOneResult]:
        async with sem:
            result = await client.evaluate(
                build_state(row.loop_title, row.text, row.inflow),
                {Q_SAME: QUESTION},
                max_attempts=1,
            )
        return row.id, result

    return dict(await asyncio.gather(*(one(r) for r in rows)))


def e5_similarity(embedder: Any, rows: list[Row]) -> dict[str, float]:
    """`find_matching_loop`'s own measure: cosine over `embedder.encode` of both titles."""
    from ze_memory.consolidation_store import _cosine_similarity

    return {
        r.id: float(
            _cosine_similarity(
                embedder.encode(r.new_title), embedder.encode(r.loop_title)
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
    points = []
    for r in rows:
        res = results[r.id]
        ans = res.answers.get(Q_SAME) if res.outcome == "ok" else None
        if ans is not None and ans.noul is not None and not math.isnan(ans.noul):
            points.append((ans.noul, r.gold_same))
    print(f"\n== Noul reliability: {Q_SAME} (n={len(points)})")
    print("bin          n   mean_noul   gold_same_rate")
    for lo, hi in zip(BINS, BINS[1:]):
        bucket = [(v, g) for v, g in points if lo <= v < hi]
        if bucket:
            print(
                f"[{lo:.1f},{min(hi, 1.0):.1f})".ljust(11)
                + f"{len(bucket):4d}   {sum(v for v, _ in bucket) / len(bucket):8.3f}"
                f"   {sum(g for _, g in bucket) / len(bucket):8.3f}"
            )


def report_grid(rows: list[Row], results: dict[str, SystemOneResult]) -> None:
    print(
        "\n== bar grid: false promotions / corroborate precision / recall"
        " (promote_hold rows, corroborate_hold cols, C <= P)"
    )
    print("P\\C        " + "".join(f"{c:>15.2f}" for c in GRID))
    for p in GRID:
        cells = ""
        for c in GRID:
            if c > p:
                cells += f"{'-':>15s}"
                continue
            counts = score(rows, kinds_for(rows, results, CorroborationSurfaceConfig(True, c, p)))
            cells += f"{counts.false_promotions:>4d}/{counts.precision:.2f}/{counts.recall:.2f}"
        print(f"{p:>8.2f}   " + cells)


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


def parse_bars(text: str) -> CorroborationSurfaceConfig:
    try:
        corroborate_hold, promote_hold = (float(x) for x in text.split(","))
    except ValueError:
        raise SystemExit("--bars needs CORROBORATE,PROMOTE, e.g. 0.6,0.85")
    if not all(0.0 <= v <= 1.0 for v in (corroborate_hold, promote_hold)):
        raise SystemExit("--bars values must be within [0, 1]")
    if corroborate_hold > promote_hold:
        raise SystemExit("--bars needs CORROBORATE <= PROMOTE")
    return CorroborationSurfaceConfig(True, corroborate_hold, promote_hold)


def config_model() -> str | None:
    system_one = (yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}).get(
        "system_one"
    ) or {}
    return system_one.get("model")


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
    problems = shape_problems(tuned, holdout)
    for p in problems:
        print("PROBLEM:", p, file=sys.stderr)
    return 1 if problems else 0


async def main_async(args: argparse.Namespace) -> int:
    if args.check_sets:
        return check_sets()
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print(
            "OPENROUTER_API_KEY is required (this run is live and costs credits).",
            file=sys.stderr,
        )
        return 2
    from ze_core.openrouter.system_one import DEFAULT_MODEL, OpenRouterSystemOneClient

    holdout = args.set == "holdout"
    rows = load_rows(HOLDOUT if holdout else TUNED)
    problems = shape_problems(load_rows(TUNED), load_rows(HOLDOUT))
    if problems:
        print("Dataset problems; run --check-sets.", file=sys.stderr)
        return 1
    if holdout and not args.bars:
        print("--set holdout needs frozen --bars CORROBORATE,PROMOTE.", file=sys.stderr)
        return 2
    if holdout:
        print(
            "WARNING: held-out verdict run. Changing wording or bars after this run voids the set;"
            " write a fresh held-out file before the next verdict (FR-020)."
        )
    system = OpenRouterSystemOneClient(
        api_key=api_key,
        model=args.model or config_model() or DEFAULT_MODEL,
        timeout_ms=args.timeout_ms,
    )
    print(f"model={system._model} set={args.set} rows={len(rows)}")
    results = await run_system_one(system, rows, args.concurrency)
    similarity = e5_similarity(get_embedder(), rows)
    e5 = e5_kinds(rows, similarity)
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
    kinds = kinds_for(rows, results, cfg)
    out = report_scores(rows, kinds, e5, by_inflow=False)
    print("\n== HELD-OUT VERDICT")
    print(f"bars: corroborate_hold={cfg.corroborate_hold} promote_hold={cfg.promote_hold}")
    overall = True
    for lang in LANGS:
        sys_c, e5_c = out[lang]
        ok, failing = verdict(sys_c, e5_c)
        overall &= ok
        print(
            f"[{lang}] {'ENABLE' if ok else 'KEEP OFF'}"
            f"  system one: P={sys_c.precision:.3f} R={sys_c.recall:.3f} ({sys_c.true_counted}/{sys_c.positives})"
            f" counted={sys_c.counted} falsePromotions={sys_c.false_promotions} fallback={sys_c.fallback}"
            f" | e5: P={e5_c.precision:.3f} R={e5_c.recall:.3f} ({e5_c.true_counted}/{e5_c.positives})"
            f" counted={e5_c.counted}"
            + (f"\n      failing: {'; '.join(failing)}" if failing else "")
        )
    print(f"OVERALL: {'ENABLE' if overall else 'KEEP OFF'}")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check-sets", action="store_true", help="offline dataset shape check")
    p.add_argument("--set", choices=("tuned", "holdout"), default="tuned")
    p.add_argument(
        "--bars", default=None, help="CORROBORATE,PROMOTE (required for --set holdout)"
    )
    p.add_argument("--model", default=None)
    p.add_argument("--timeout-ms", type=int, default=10_000)
    p.add_argument("--concurrency", type=int, default=4)
    return p


def main() -> None:
    args = parser().parse_args()
    args.bars_cfg = parse_bars(args.bars) if args.bars else None
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
