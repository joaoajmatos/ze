"""Calibration for the loop-gate System One surface (phase 168).

`make calibrate-loop-gate` calls the real System One endpoint over the tuned set
(eval/calibration/loop_gate.jsonl) and, side by side, the production 109 Haiku gate as the
baseline. It costs credits and is never collected by pytest.

- Default `--set tuned`: per language and provenance precision, recall, false creates, false
  resolve, false declared, explicit and resolves accuracy, a reliability table per Noul, and
  suggested bars chosen on the tuned set only. Held-out rows are never read or printed.
- `--set holdout --bars LOOP,RESOLVES`: the single verdict run on
  eval/calibration/loop_gate_holdout.jsonl with frozen wording and bars. ENABLE or KEEP OFF per
  language, with the failing clause. Tuning after this run voids the set (FR-016): write a new
  held-out file before the next verdict.
- `--check-sets`: offline. Dataset shape only, no network.

Acceptance rule per language (FR-018): zero false creates on gold-negative rows, recall >=
Haiku recall - 0.05, precision >= Haiku precision.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ze_agents.system_one import SystemOneResult
from ze_worldstate.extraction import (
    DEFAULT_EXTRACTION_MODEL,
    _SYSTEM_PROMPT,
    _ExtractionGateResult,
    _loads_json,
    _run_extraction_gate,
)
from ze_worldstate.loop_judge import (
    LOOP_QUESTIONS,
    Q_CONCERN,
    Q_RESOLVES,
    LoopGateSurfaceConfig,
    build_state,
    decide,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402

TUNED = Path(__file__).with_name("loop_gate.jsonl")
HOLDOUT = Path(__file__).with_name("loop_gate_holdout.jsonl")
LANGS = harness.LANGS
PROVENANCES = ("conversation", "email", "calendar", "ingestion")
# Conversation turns are judged by the commitment intake (173), not by this gate. Their rows stay
# in the files and in the shape check, and live runs skip them.
GRID = harness.GRID
MIN_TUNED_PER_LANG = 40
MIN_HOLDOUT_PER_LANG = 20
RECALL_SLACK = 0.05
CREATES = ("create_declared", "create_suspected")


@dataclass
class Row:
    id: str
    lang: str
    provenance: str
    text: str
    gold_loop: bool
    gold_explicit: bool
    gold_resolves: bool
    kind: str


load_rows = harness.row_loader(Row)


def shape_problems(tuned: list[Row], holdout: list[Row]) -> list[str]:
    problems: list[str] = []
    for name, rows, minimum in (
        ("tuned", tuned, MIN_TUNED_PER_LANG),
        ("holdout", holdout, MIN_HOLDOUT_PER_LANG),
    ):
        problems += harness.min_rows_problems(name, rows, minimum)
        for lang in LANGS:
            for prov in PROVENANCES:
                sub = [r for r in rows if r.lang == lang and r.provenance == prov]
                if not any(r.gold_loop for r in sub):
                    problems.append(f"{name}/{lang}/{prov}: no positive row")
                if not any(not r.gold_loop for r in sub):
                    problems.append(f"{name}/{lang}/{prov}: no negative row")
        for r in rows:
            if r.lang not in LANGS or r.provenance not in PROVENANCES:
                problems.append(f"{name}/{r.id}: bad lang or provenance")
            if r.gold_explicit and not (r.gold_loop and r.provenance == "conversation"):
                problems.append(
                    f"{name}/{r.id}: gold_explicit needs a conversation loop"
                )
            if r.gold_resolves and r.gold_loop:
                problems.append(f"{name}/{r.id}: gold_resolves with gold_loop")
    return problems + harness.split_problems(tuned, holdout)


# --- decisions -----------------------------------------------------------------------


def gate_config(loop_hold: float, resolves_hold: float) -> LoopGateSurfaceConfig:
    return harness.surface_config(
        LoopGateSurfaceConfig, loop_hold=loop_hold, resolves_hold=resolves_hold
    )


def system_one_kind(
    result: SystemOneResult, cfg: LoopGateSurfaceConfig, provenance: str
) -> str:
    return decide(result, cfg, provenance).kind


def haiku_kind(gate: _ExtractionGateResult | None) -> str:
    if gate is None:
        return "fallback"
    if gate.resolves_existing and gate.title:
        return "resolve"
    if gate.is_loop and gate.title:
        return "create_declared" if gate.explicit_declaration else "create_suspected"
    return "hold"


# --- metrics -------------------------------------------------------------------------


@dataclass
class Counts:
    n: int = 0
    fallback: int = 0
    positives: int = 0
    hit_positives: int = 0
    creates: int = 0
    correct_creates: int = 0
    false_creates: int = 0
    false_resolve: int = 0
    false_declared: int = 0
    explicit_total: int = 0
    explicit_ok: int = 0
    resolves_ok: int = 0

    @property
    def precision(self) -> float:
        return self.correct_creates / self.creates if self.creates else 1.0

    @property
    def recall(self) -> float:
        return self.hit_positives / self.positives if self.positives else 0.0

    @property
    def explicit_acc(self) -> float:
        return self.explicit_ok / self.explicit_total if self.explicit_total else 1.0

    @property
    def resolves_acc(self) -> float:
        return self.resolves_ok / self.n if self.n else 1.0


def score(rows: list[Row], kinds: dict[str, str]) -> Counts:
    """A `fallback` row counts as a miss (no create); it is never a false create."""
    c = Counts()
    for r in rows:
        kind = kinds[r.id]
        c.n += 1
        c.fallback += kind == "fallback"
        create = kind in CREATES
        c.positives += r.gold_loop
        c.creates += create
        if create and r.gold_loop:
            c.correct_creates += 1
            c.hit_positives += 1
        if create and not r.gold_loop:
            c.false_creates += 1
        if kind == "resolve" and not r.gold_resolves:
            c.false_resolve += 1
        if kind == "create_declared" and not r.gold_explicit:
            c.false_declared += 1
        if r.provenance == "conversation":
            c.explicit_total += 1
            c.explicit_ok += (kind == "create_declared") == r.gold_explicit
        c.resolves_ok += (kind == "resolve") == r.gold_resolves
    return c


def verdict(system: Counts, haiku: Counts) -> tuple[bool, list[str]]:
    failing: list[str] = []
    if system.false_creates:
        failing.append(f"false creates {system.false_creates} != 0")
    if system.recall < haiku.recall - RECALL_SLACK:
        failing.append(
            f"recall {system.recall:.3f} < Haiku {haiku.recall:.3f} - {RECALL_SLACK}"
        )
    if system.precision < haiku.precision:
        failing.append(
            f"precision {system.precision:.3f} < Haiku {haiku.precision:.3f}"
        )
    return not failing, failing


def _kinds_for(
    rows: list[Row], results: dict[str, SystemOneResult], cfg: LoopGateSurfaceConfig
) -> dict[str, str]:
    return {r.id: system_one_kind(results[r.id], cfg, r.provenance) for r in rows}


def _median(values: list[float]) -> float:
    return round(statistics.median(values), 2)


def suggest_bars(
    rows: list[Row], results: dict[str, SystemOneResult]
) -> LoopGateSurfaceConfig | None:
    """Zero false creates, then zero false resolves, then max recall; centre of the plateau."""
    best_key: tuple | None = None
    plateau: list[tuple[float, float]] = []
    for loop_hold in GRID:
        for resolves_hold in GRID:
            cfg = gate_config(loop_hold, resolves_hold)
            c = score(rows, _kinds_for(rows, results, cfg))
            key = (c.false_creates, c.false_resolve, -c.recall)
            if best_key is None or key < best_key:
                best_key, plateau = key, [(loop_hold, resolves_hold)]
            elif key == best_key:
                plateau.append((loop_hold, resolves_hold))
    if best_key is None or best_key[0] != 0:
        return None
    loop_hold = _median([p[0] for p in plateau])
    resolves_hold = _median([p[1] for p in plateau])
    return gate_config(loop_hold, resolves_hold)


# --- live runs -----------------------------------------------------------------------


async def run_haiku(
    llm: Any, rows: list[Row], model: str, concurrency: int
) -> dict[str, _ExtractionGateResult | None]:
    gates = await harness.bounded(
        rows, lambda _, r: _run_extraction_gate(r.text, llm, model), concurrency
    )
    return {r.id: gate for r, gate in zip(rows, gates)}


async def run_haiku_tolerant(
    llm: Any, rows: list[Row], model: str, concurrency: int
) -> dict[str, _ExtractionGateResult | None]:
    """The 109 prompt and fields, but tolerant of the ```json fence Haiku wraps replies in.

    The production gate calls json.loads on the raw reply and so fails on every fenced answer.
    This is the working-gate baseline the verdict compares against.
    """

    async def one(_: int, row: Row) -> _ExtractionGateResult | None:
        try:
            raw = await llm.complete(
                [{"role": "user", "content": row.text}],
                model=model,
                system=_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            parsed = _loads_json(raw)
        except Exception:
            return None
        window = parsed.get("implied_window_days")
        return _ExtractionGateResult(
            is_loop=bool(parsed.get("is_loop")),
            title=str(parsed.get("title") or "").strip(),
            explicit_declaration=bool(parsed.get("explicit_declaration")),
            resolves_existing=bool(parsed.get("resolves_existing")),
            implied_window_days=int(window)
            if isinstance(window, (int, float))
            else None,
        )

    gates = await harness.bounded(rows, one, concurrency)
    return {r.id: gate for r, gate in zip(rows, gates)}


# --- reports -------------------------------------------------------------------------


def _fmt(c: Counts) -> str:
    return (
        f"n={c.n} fb={c.fallback} P={c.precision:.3f} R={c.recall:.3f} "
        f"({c.hit_positives}/{c.positives}) creates={c.creates} falseC={c.false_creates} "
        f"falseRes={c.false_resolve} resAcc={c.resolves_acc:.3f}"
    )


def report_scores(
    rows: list[Row],
    system_kinds: dict[str, str],
    haiku_kinds: dict[str, str],
    *,
    by_provenance: bool,
) -> dict[str, tuple[Counts, Counts]]:
    out: dict[str, tuple[Counts, Counts]] = {}
    for lang in (*LANGS, "all"):
        scoped = [r for r in rows if lang == "all" or r.lang == lang]
        out[lang] = (score(scoped, system_kinds), score(scoped, haiku_kinds))
        print(f"\n== [{lang}]")
        print("  system one: " + _fmt(out[lang][0]))
        print("  haiku(tol): " + _fmt(out[lang][1]))
        if by_provenance:
            for prov in PROVENANCES:
                sub = [r for r in scoped if r.provenance == prov]
                if sub:
                    print(
                        f"  {prov:<12s} s1: {_fmt(score(sub, system_kinds))}\n"
                        f"  {'':<12s} hk: {_fmt(score(sub, haiku_kinds))}"
                    )
    return out


def show_reliability(rows: list[Row], results: dict[str, SystemOneResult]) -> None:
    gold = {Q_CONCERN: lambda r: r.gold_loop, Q_RESOLVES: lambda r: r.gold_resolves}
    for qid, truth in gold.items():
        points = [
            (ans.noul, truth(r))
            for r in rows
            if results[r.id].outcome == "ok"
            if (ans := results[r.id].answers.get(qid)) and ans.noul is not None
        ]
        harness.print_reliability(
            f"Noul reliability: {qid} (n={len(points)})",
            harness.reliability_bins(points, harness.NOUL_EDGES),
            "mean_noul",
            "gold_pos_rate",
        )


def show_grid(rows: list[Row], results: dict[str, SystemOneResult]) -> None:
    def cell(bars: dict[str, float]) -> Counts:
        cfg = gate_config(bars["loop"], bars["res"])
        return score(rows, _kinds_for(rows, results, cfg))

    harness.print_grid(
        "bar grid: false creates / recall (loop_hold rows, resolves_hold cols)",
        "loop\\res   ",
        harness.bar_grid({"loop": GRID, "res": GRID}, cell),
        "loop",
        "res",
        lambda c: f"{c.false_creates:>5d}/{c.recall:<4.2f}",
        width=10,
        label_width=8,
    )


def report_errors(
    rows: list[Row], results: dict[str, SystemOneResult], kinds: dict[str, str]
) -> None:
    """Tuned set only: every row the gate gets wrong, with its Noul values."""
    print(
        "\n== tuned-set errors at the bars used (id, kind, gold -> decision, noul values)"
    )
    for r in rows:
        kind = kinds[r.id]
        gold = "resolve" if r.gold_resolves else ("loop" if r.gold_loop else "none")
        got = (
            "resolve" if kind == "resolve" else ("loop" if kind in CREATES else "none")
        )
        if gold == got and (kind == "create_declared") == r.gold_explicit:
            continue
        answers = results[r.id].answers
        vals = " ".join(
            f"{qid[:7]}={answers[qid].noul:.2f}"
            for qid in answers
            if answers[qid].noul is not None
        )
        print(
            f"  {r.id} {r.kind}: gold {gold}/{'expl' if r.gold_explicit else '-'} -> {kind}  {vals}"
        )


# --- main ----------------------------------------------------------------------------


def check_sets() -> int:
    tuned, holdout = load_rows(TUNED), load_rows(HOLDOUT)
    for name, rows in (("tuned", tuned), ("holdout", holdout)):
        print(f"{name}: {len(rows)} rows")
        for lang in LANGS:
            pos = sum(r.gold_loop for r in rows if r.lang == lang)
            tot = sum(r.lang == lang for r in rows)
            print(f"  {lang}: {tot} rows, {pos} positive, {tot - pos} negative")
    return harness.shape_report(shape_problems(tuned, holdout))


def system_one_detail(c: Counts, h: Counts) -> str:
    return (
        f"system one: P={c.precision:.3f} R={c.recall:.3f} ({c.hit_positives}/{c.positives})"
        f" creates={c.creates} falseCreates={c.false_creates} fallback={c.fallback}"
        f" | haiku: P={h.precision:.3f} R={h.recall:.3f} ({h.hit_positives}/{h.positives})"
        f" creates={h.creates} falseCreates={h.false_creates}"
    )


async def main_async(args: argparse.Namespace) -> int:
    if args.check_sets:
        return check_sets()
    holdout = args.set == "holdout"
    rows = [
        r
        for r in load_rows(HOLDOUT if holdout else TUNED)
        if r.provenance != "conversation"
    ]
    if shape_problems(load_rows(TUNED), load_rows(HOLDOUT)):
        print("Dataset problems; run --check-sets.", file=sys.stderr)
        return 1
    if holdout and not args.bars:
        print("--set holdout needs frozen --bars LOOP,RESOLVES.", file=sys.stderr)
        return 2
    if holdout:
        harness.held_out_warning("FR-016")
    results = await harness.collect(
        args,
        rows,
        lambda r: build_state(r.text, r.provenance),
        lambda _, r: dict(LOOP_QUESTIONS),
        lambda model: (
            f"model={model} haiku={args.haiku_model} set={args.set} rows={len(rows)}"
        ),
    )
    if results is None or (key := harness.api_key()) is None:
        return 2
    from ze_core.openrouter.client import OpenRouterClient
    from ze_core.openrouter.system_one import DEFAULT_BASE_URL

    llm = OpenRouterClient(api_key=key, base_url=DEFAULT_BASE_URL)
    prod_gates = await run_haiku(llm, rows, args.haiku_model, args.concurrency)
    haiku_gates = await run_haiku_tolerant(llm, rows, args.haiku_model, args.concurrency)
    await llm.aclose()
    skipped = Counter(r.skip_reason for r in results.values() if r.outcome == "skip")
    if skipped:
        print(
            f"system one skipped rows (count as misses, never false creates): {dict(skipped)}"
        )
    haiku_kinds = {rid: haiku_kind(g) for rid, g in haiku_gates.items()}
    prod_kinds = {rid: haiku_kind(g) for rid, g in prod_gates.items()}
    prod = score(rows, prod_kinds)
    print(
        "\nproduction 109 gate as-is (json.loads, no fence handling): "
        f"{prod.fallback}/{prod.n} replies unparseable; " + _fmt(prod)
    )
    print(
        "baseline below = the same prompt, fence-tolerant (what the 109 gate does when it parses)"
    )

    if not holdout:
        show_reliability(rows, results)
        show_grid(rows, results)
        suggestion = suggest_bars(rows, results)
        cfg = args.bars_cfg or suggestion
        if cfg is None:
            print("\nNo bar pair reaches zero false creates on this set.")
            cfg = gate_config(0.9, 0.9)
            report_scores(rows, _kinds_for(rows, results, cfg), haiku_kinds, by_provenance=True)
            return 0
        kinds = _kinds_for(rows, results, cfg)
        print(
            f"\nbars used: loop_hold={cfg.loop_hold} resolves_hold={cfg.resolves_hold}"
        )
        report_scores(rows, kinds, haiku_kinds, by_provenance=True)
        report_errors(rows, results, kinds)
        if suggestion:
            print(
                "\nSuggested bars (tuned set only): "
                f"loop_hold: {suggestion.loop_hold}  resolves_hold: {suggestion.resolves_hold}"
            )
        return 0

    cfg = args.bars_cfg
    out = report_scores(rows, _kinds_for(rows, results, cfg), haiku_kinds, by_provenance=False)
    harness.print_verdict(
        {
            lang: (*verdict(*out[lang]), system_one_detail(*out[lang]))
            for lang in LANGS
        },
        lead=[f"bars: loop_hold={cfg.loop_hold} resolves_hold={cfg.resolves_hold}"],
    )
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    harness.common_args(
        p, sets=("tuned", "holdout"), bars="LOOP,RESOLVES (required for --set holdout)"
    )
    p.add_argument("--haiku-model", default=DEFAULT_EXTRACTION_MODEL)
    return p


def main() -> None:
    args = parser().parse_args()
    args.bars_cfg = (
        harness.bars_config(LoopGateSurfaceConfig, args.bars, ("loop_hold", "resolves_hold"))
        if args.bars
        else None
    )
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
