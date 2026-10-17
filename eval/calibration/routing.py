"""Opt-in live calibration for the routing System One surface (phase 164).

Calls the real System One endpoint over eval/calibration/routing.jsonl, costs
credits, and is never collected by pytest. Run it with `make calibrate-routing`.

Per row it builds the production shortlist with the local E5 singleton (the same
`judge.shortlist` helper as the router), asks the production questions with the
option order shuffled (eval only), then reports:

- Choice accuracy against the gold agent and a peakedness reliability table;
- `none` precision and recall;
- Noul separation for gold-mixed versus single rows;
- a grid of `choice_trust` x `multi_specialist_hold` with the 160 false compounds
  each pair would remove and the harmful trusts it would add;
- suggested values for `choice_trust` and `multi_specialist_hold`.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import importlib.util
import json
import os
import random
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ze_agents.defaults import ROUTING_GAP_THRESHOLD, ROUTING_THRESHOLD
from ze_agents.registry import get_enabled_agents
from ze_agents.system_one import SystemOneResult
from ze_core.orchestration.judgment_state import with_screen_line
from ze_core.openrouter.system_one import DEFAULT_MODEL, OpenRouterSystemOneClient
from ze_core.routing.judge import (
    DEFAULT_SHORTLIST_K,
    RoutingSurfaceConfig,
    build_questions,
    build_state,
    criterion_for,
    decide,
    shortlist,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET = Path(__file__).with_name("routing.jsonl")
CONFIG = ROOT / "apps" / "ze-api" / "config" / "config.yaml"
AGENT_MODULES = (
    ROOT / "core" / "engine" / "ze-core" / "tests" / "support" / "agent_modules.py"
)
GRID = [round(0.5 + 0.05 * i, 2) for i in range(10)]
BINS = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0001]


@dataclass
class Row:
    id: str
    lang: str
    prompt: str
    gold_agent: str
    gold_multi: bool
    history: str | None = None
    screen: str | None = None


@dataclass
class Outcome:
    """One row after the E5 shortlist and one System One request."""

    row: Row
    names: list[str]
    cosine_top: float
    cosine_gap: float
    result: SystemOneResult

    @property
    def ok(self) -> bool:
        return self.result.outcome == "ok"

    @property
    def would_decompose_160(self) -> bool:
        return (
            self.cosine_top < ROUTING_THRESHOLD
            or self.cosine_gap < ROUTING_GAP_THRESHOLD
        )


def load_rows(path: Path) -> list[Row]:
    rows = [
        Row(
            id=raw["id"],
            lang=raw["lang"],
            prompt=raw["prompt"],
            gold_agent=raw["gold_agent"],
            gold_multi=raw["gold_multi"],
            history=raw.get("history"),
            screen=raw.get("screen"),
        )
        for raw in (
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    ]
    if len({r.id for r in rows}) != len(rows):
        raise SystemExit("duplicate ids in calibration set")
    return rows


def load_roster() -> tuple[dict[str, str], dict[str, str]]:
    """Enabled agents: (descriptions for E5, Choice criteria as production builds them)."""
    from ze_agents.bootstrap import reload_agent_modules

    spec = importlib.util.spec_from_file_location(
        "_routing_agent_modules", AGENT_MODULES
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reload_agent_modules(module.ALL_AGENT_MODULE_PATHS)
    enabled = sorted(get_enabled_agents().items())
    return (
        {name: cls.description.strip() for name, cls in enabled},
        {name: criterion_for(cls) for name, cls in enabled},
    )


def rank(embedder: Any, roster: dict[str, str], text: str) -> list[tuple[str, float]]:
    names = sorted(roster)
    matrix = embedder.encode_passage(
        [roster[n] for n in names], normalize_embeddings=True
    )
    vec = embedder.encode_query(text, normalize_embeddings=True)
    scores = (matrix @ vec).tolist()
    return sorted(zip(names, scores), key=lambda p: p[1], reverse=True)


RECALL_BAR = 0.95


def recall_ks(roster: dict[str, str]) -> tuple[int, ...]:
    return tuple(range(2, len(roster) + 1))


def shortlist_recall(
    embedder: Any,
    roster: dict[str, str],
    rows: list[Row],
    ks: tuple[int, ...] | None = None,
) -> dict[int, list[Row]]:
    """Rows whose gold agent is outside the E5 top-k, per k. Offline: no System One call."""
    ks = ks or recall_ks(roster)
    misses: dict[int, list[Row]] = {k: [] for k in ks}
    for row in rows:
        if row.gold_agent not in roster:
            continue
        text = row.prompt if not row.history else f"{row.prompt}\n\n{row.history}"
        ranked = [n for n, _ in rank(embedder, roster, text)]
        for k in ks:
            if row.gold_agent not in shortlist(ranked, k):
                misses[k].append(row)
    return misses


def recall_by_k(scored: int, misses: dict[int, list[Row]]) -> dict[int, float]:
    return {k: (scored - len(m)) / scored if scored else 1.0 for k, m in misses.items()}


def smallest_passing_k(per_set: list[dict[int, float]]) -> int | None:
    """Smallest k whose recall is at least RECALL_BAR on every set, or None."""
    if not per_set:
        return None
    for k in sorted(per_set[0]):
        if all(recall[k] >= RECALL_BAR for recall in per_set):
            return k
    return None


def report_recall(
    embedder: Any,
    roster: dict[str, str],
    datasets: dict[str, list[Row]],
    ks: tuple[int, ...] | None = None,
) -> int | None:
    ks = ks or recall_ks(roster)
    per_set: list[dict[int, float]] = []
    for name, rows in datasets.items():
        scored = [r for r in rows if r.gold_agent in roster]
        misses = shortlist_recall(embedder, roster, rows, ks)
        recall = recall_by_k(len(scored), misses)
        per_set.append(recall)
        print(
            f"\n== {name}: E5 shortlist recall of the gold agent ({len(scored)} rows with a gold agent)"
        )
        print("k     recall   missed")
        for k in ks:
            print(f"{k:<5d} {recall[k]:.3f}    {len(misses[k])}")
        by_agent: Counter[str] = Counter(r.gold_agent for r in misses[ks[0]])
        print(f"missed at k={ks[0]} by gold agent: {dict(by_agent)}")
    best = smallest_passing_k(per_set)
    print(
        f"\nSmallest k with recall >= {RECALL_BAR} on every set: "
        f"{best if best is not None else 'none'}"
    )
    return best


def shuffled_questions(criteria: dict[str, str], names: list[str], rng: random.Random):
    order = list(names)
    rng.shuffle(order)
    return build_questions({n: criteria[n] for n in order})


async def run_rows(
    client: Any,
    embedder: Any,
    roster: dict[str, str],
    criteria: dict[str, str],
    rows: list[Row],
    *,
    seed: int,
    concurrency: int,
    k: int,
) -> list[Outcome]:
    sem = asyncio.Semaphore(concurrency)

    async def one(index: int, row: Row) -> Outcome:
        text = row.prompt if not row.history else f"{row.prompt}\n\n{row.history}"
        ranked = rank(embedder, roster, text)
        names = shortlist([n for n, _ in ranked], k)
        questions = shuffled_questions(
            criteria, names, random.Random(seed * 100003 + index)
        )
        state = build_state(
            row.prompt, row.history, with_screen_line(None, row.screen)
        )
        async with sem:
            result = await client.evaluate(state, questions, max_attempts=1)
        return Outcome(row, names, ranked[0][1], ranked[0][1] - ranked[1][1], result)

    return list(await asyncio.gather(*(one(i, r) for i, r in enumerate(rows))))


def predicted(outcome: Outcome) -> tuple[str | None, float | None]:
    answer = outcome.result.answers.get("agent")
    if answer is None:
        return None, None
    return answer.choice, answer.confidence


def single_rows(outcomes: list[Outcome]) -> list[Outcome]:
    return [o for o in outcomes if o.ok and not o.row.gold_multi]


def report_accuracy(outcomes: list[Outcome]) -> None:
    for lang in ("en", "pt"):
        scoped = [o for o in single_rows(outcomes) if o.row.lang == lang]
        hits = sum(predicted(o)[0] == o.row.gold_agent for o in scoped)
        if scoped:
            print(
                f"\n== [{lang}] Choice accuracy vs gold agent: {hits}/{len(scoped)} = {hits / len(scoped):.3f}"
            )
        misses = [o for o in scoped if predicted(o)[0] != o.row.gold_agent]
        for o in misses:
            print(f"   miss {o.row.id}: gold={o.row.gold_agent} pred={predicted(o)[0]}")
    outside = [
        o for o in single_rows(outcomes) if o.row.gold_agent not in o.names + ["none"]
    ]
    print(
        f"\ngold agent outside the shortlist (k too small?): {len(outside)}"
        + "".join(
            f"\n   {o.row.id}: gold={o.row.gold_agent} shortlist={o.names}"
            for o in outside
        )
    )


def reliability_points(outcomes: list[Outcome]) -> list[tuple[float, bool]]:
    return [
        (conf, choice == o.row.gold_agent)
        for o in single_rows(outcomes)
        for choice, conf in [predicted(o)]
        if conf is not None
    ]


def ece(outcomes: list[Outcome]) -> float | None:
    points = reliability_points(outcomes)
    if not points:
        return None
    total = 0.0
    for lo, hi in zip(BINS, BINS[1:]):
        bucket = [(c, ok) for c, ok in points if lo <= c < hi]
        if bucket:
            conf = sum(c for c, _ in bucket) / len(bucket)
            acc = sum(ok for _, ok in bucket) / len(bucket)
            total += len(bucket) * abs(conf - acc)
    return total / len(points)


def report_reliability(outcomes: list[Outcome]) -> None:
    print("\n== Choice peakedness reliability")
    print("bin          n   mean_conf   accuracy")
    points = reliability_points(outcomes)
    for lo, hi in zip(BINS, BINS[1:]):
        bucket = [(c, ok) for c, ok in points if lo <= c < hi]
        if bucket:
            conf = sum(c for c, _ in bucket) / len(bucket)
            acc = sum(ok for _, ok in bucket) / len(bucket)
            print(
                f"[{lo:.1f},{min(hi, 1.0):.1f})".ljust(11)
                + f"{len(bucket):4d}   {conf:8.3f}   {acc:8.3f}"
            )
    value = ece(outcomes)
    if value is not None:
        print(f"ECE = {value:.3f}")


def report_none(outcomes: list[Outcome]) -> None:
    scoped = single_rows(outcomes)
    tp = sum(predicted(o)[0] == "none" and o.row.gold_agent == "none" for o in scoped)
    fp = sum(predicted(o)[0] == "none" and o.row.gold_agent != "none" for o in scoped)
    fn = sum(predicted(o)[0] != "none" and o.row.gold_agent == "none" for o in scoped)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    print(
        f"\n== none: precision {precision:.2f} recall {recall:.2f} (tp={tp} fp={fp} fn={fn})"
    )


def noul_values(outcomes: list[Outcome], multi: bool) -> list[float]:
    values = []
    for o in outcomes:
        answer = o.result.answers.get("multi_specialist") if o.ok else None
        if answer is not None and answer.noul is not None and o.row.gold_multi == multi:
            values.append(answer.noul)
    return values


def report_noul(outcomes: list[Outcome]) -> None:
    mixed, single = noul_values(outcomes, True), noul_values(outcomes, False)
    print("\n== multiple-specialist Noul")
    for label, values in (("gold mixed", mixed), ("gold single", single)):
        if values:
            print(
                f"{label:12s} n={len(values):3d} mean={statistics.mean(values):.2f}"
                f" min={min(values):.2f} max={max(values):.2f}"
            )


def grid_metrics(outcomes: list[Outcome]) -> list[dict[str, float]]:
    scored = [o for o in outcomes if o.ok]
    out = []
    for trust in GRID:
        for hold in GRID:
            cfg = RoutingSurfaceConfig(
                enabled=True, choice_trust=trust, multi_specialist_hold=hold
            )
            removed = harmful = 0
            for o in scored:
                decision = decide(o.result, cfg, o.names)
                if decision.kind != "trust":
                    continue
                correct = (
                    not o.row.gold_multi
                    and o.row.gold_agent not in ("none",)
                    and decision.agent == o.row.gold_agent
                )
                if correct and o.would_decompose_160:
                    removed += 1
                elif not correct:
                    harmful += 1
            out.append(
                {"trust": trust, "hold": hold, "removed": removed, "harmful": harmful}
            )
    return out


def report_grid(metrics: list[dict[str, float]]) -> tuple[float, float] | None:
    print(
        "\n== false compounds removed / harmful trusts (choice_trust rows, multi_specialist_hold cols)"
    )
    print("trust\\hold ".ljust(11) + "".join(f"{h:>10.2f}" for h in GRID))
    by_pair = {(m["trust"], m["hold"]): m for m in metrics}
    for t in GRID:
        cells = "".join(
            f"{int(by_pair[(t, h)]['removed']):>6d}/{int(by_pair[(t, h)]['harmful']):<3d}"
            for h in GRID
        )
        print(f"{t:>9.2f}  " + cells)
    safe = [m for m in metrics if m["harmful"] == 0 and m["removed"] > 0]
    if not safe:
        print(
            "\nNo bar pair removes a false compound with zero harmful trusts on this set."
        )
        return None
    best = max(safe, key=lambda m: (m["removed"], -(m["trust"] + m["hold"])))
    print(
        f"\nSuggested: choice_trust: {best['trust']}  multi_specialist_hold: {best['hold']}"
        f"  (removes {int(best['removed'])} false compounds, 0 harmful trusts)"
    )
    return best["trust"], best["hold"]


ACCURACY_BAR = 0.95
ECE_BAR = 0.10
RESEARCH_GOLD = "research"
COMPANION = "companion"


def lang_accuracy(outcomes: list[Outcome], lang: str) -> tuple[int, int]:
    scoped = [o for o in single_rows(outcomes) if o.row.lang == lang]
    return sum(predicted(o)[0] == o.row.gold_agent for o in scoped), len(scoped)


def research_to_companion_misses(
    outcomes: list[Outcome], trust: float | None = None
) -> int:
    """Gold-research rows answered companion; with ``trust`` only those that bar would trust."""
    count = 0
    for o in single_rows(outcomes):
        choice, conf = predicted(o)
        if o.row.gold_agent == RESEARCH_GOLD and choice == COMPANION:
            if trust is None or (conf or 0.0) >= trust:
                count += 1
    return count


@dataclass
class SetVerdict:
    name: str
    lines: list[str]
    passed: bool


def verdict_for_set(name: str, outcomes: list[Outcome]) -> SetVerdict:
    lines: list[str] = []
    passed = True
    for lang in ("en", "pt"):
        hits, total = lang_accuracy(outcomes, lang)
        if not total:
            continue
        ok = hits / total >= ACCURACY_BAR
        passed &= ok
        lines.append(
            f"{'PASS' if ok else 'FAIL'}  [{lang}] accuracy {hits}/{total} = {hits / total:.3f} (>= {ACCURACY_BAR})"
        )
    value = ece(outcomes)
    if value is not None:
        ok = value <= ECE_BAR
        passed &= ok
        lines.append(f"{'PASS' if ok else 'FAIL'}  ECE {value:.3f} (<= {ECE_BAR})")
    clean = [t for t in GRID if research_to_companion_misses(outcomes, t) == 0]
    ok = bool(clean)
    passed &= ok
    detail = (
        f"lowest choice_trust with zero trusted misses: {clean[0]:.2f}"
        if clean
        else "no choice_trust in the grid removes every trusted miss"
    )
    lines.append(
        f"{'PASS' if ok else 'FAIL'}  research->companion trusted misses == 0 ({detail}; "
        f"raw misses {research_to_companion_misses(outcomes)})"
    )
    for trust in GRID:
        lines.append(
            f"      research->companion misses trusted at choice_trust {trust:.2f}: "
            f"{research_to_companion_misses(outcomes, trust)}"
        )
    return SetVerdict(name, lines, passed)


def report_verdicts(by_set: dict[str, list[Outcome]]) -> list[SetVerdict]:
    verdicts = [verdict_for_set(n, o) for n, o in by_set.items()]
    print("\n== Acceptance verdict (per set)")
    for v in verdicts:
        print(f"\n[{v.name}] {'PASS' if v.passed else 'FAIL'}")
        for line in v.lines:
            print(f"  {line}")
    overall = all(v.passed for v in verdicts)
    print(f"\nOVERALL: {'PASS' if overall else 'FAIL'}")
    return verdicts


def report(outcomes: list[Outcome], quiet: bool = False) -> dict[str, float | None]:
    if quiet:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            return report(outcomes)
    report_accuracy(outcomes)
    report_reliability(outcomes)
    report_none(outcomes)
    report_noul(outcomes)
    pair = report_grid(grid_metrics(outcomes))
    suggestion = {
        "choice_trust": pair[0] if pair else None,
        "multi_specialist_hold": pair[1] if pair else None,
    }
    return suggestion


SET_PATHS = (
    DATASET,
    DATASET.with_name("routing_holdout.jsonl"),
    DATASET.with_name("routing_holdout2.jsonl"),
    DATASET.with_name("routing_screen.jsonl"),
)
REQUIRED_KEYS = {"id", "lang", "prompt", "gold_agent", "gold_multi"}
OPTIONAL_KEYS = {"history", "screen"}
LANGS = ("en", "pt")


def set_problems(name: str, raws: list[dict]) -> list[str]:
    problems: list[str] = []
    ids: set[str] = set()
    for i, raw in enumerate(raws, 1):
        where = f"{name} row {i}"
        keys = set(raw)
        if missing := REQUIRED_KEYS - keys:
            problems.append(f"{where}: missing {sorted(missing)}")
        if extra := keys - REQUIRED_KEYS - OPTIONAL_KEYS:
            problems.append(f"{where}: unknown keys {sorted(extra)}")
        if raw.get("lang") not in LANGS:
            problems.append(f"{where}: lang must be one of {LANGS}")
        for key in ("id", "prompt", "gold_agent"):
            if not isinstance(raw.get(key), str) or not raw.get(key):
                problems.append(f"{where}: {key} must be a non-empty string")
        if not isinstance(raw.get("gold_multi"), bool):
            problems.append(f"{where}: gold_multi must be a bool")
        for key in OPTIONAL_KEYS & keys:
            if not isinstance(raw[key], str) or not raw[key].strip():
                problems.append(f"{where}: {key} must be a non-empty string")
        if raw.get("id") in ids:
            problems.append(f"{where}: duplicate id")
        ids.add(raw.get("id"))
    return problems


def check_sets(paths: tuple[Path, ...] = SET_PATHS) -> int:
    """Offline: schema and per-language row counts. No network, no row text printed."""
    problems: list[str] = []
    for path in paths:
        if not path.exists():
            problems.append(f"{path.name}: missing")
            continue
        raws = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        counts = Counter(r.get("lang") for r in raws)
        shown = " ".join(f"{lang}={counts.get(lang, 0)}" for lang in LANGS)
        print(f"{path.stem}: {len(raws)} rows ({shown})")
        problems += set_problems(path.stem, raws)
        for lang in LANGS:
            if not counts.get(lang):
                problems.append(f"{path.stem}: no {lang} rows")
    for problem in problems:
        print(f"PROBLEM {problem}", file=sys.stderr)
    return 1 if problems else 0


def system_one_config() -> dict:
    return (yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}).get(
        "system_one"
    ) or {}


async def main_async(args: argparse.Namespace) -> int:
    if args.recall:
        from ze_core.embeddings import get_embedder

        report_recall(
            get_embedder(),
            load_roster()[0],
            {path.stem: load_rows(path) for path in args.dataset},
        )
        return 0
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print(
            "OPENROUTER_API_KEY is required (this run is live and costs credits).",
            file=sys.stderr,
        )
        return 2
    from ze_core.embeddings import get_embedder

    config = system_one_config()
    client = OpenRouterSystemOneClient(
        api_key=api_key,
        model=args.model or config.get("model", DEFAULT_MODEL),
        timeout_ms=args.timeout_ms,
    )
    roster, criteria = load_roster()
    embedder = get_embedder()
    print(f"model={client._model} agents={len(roster)} k={args.k} seed={args.seed}")
    by_set: dict[str, list[Outcome]] = {}
    for path in args.dataset:
        rows = load_rows(path)
        print(f"\n######## {path.stem} ({len(rows)} rows)")
        outcomes = await run_rows(
            client,
            embedder,
            roster,
            criteria,
            rows,
            seed=args.seed,
            concurrency=args.concurrency,
            k=args.k,
        )
        skipped = Counter(o.result.skip_reason for o in outcomes if not o.ok)
        if skipped:
            print(f"skipped rows (excluded from metrics): {dict(skipped)}")
        if not any(o.ok for o in outcomes):
            print("Every call was skipped; nothing to calibrate.", file=sys.stderr)
            return 1
        report(outcomes)
        by_set[path.stem] = outcomes
    verdicts = report_verdicts(by_set)
    passing = [o for v in verdicts if v.passed for o in by_set[v.name]]
    if not passing:
        print("\nNo set passes; no bars are suggested.")
        return 0
    suggestion = report(passing, quiet=True)
    print(
        "\nSuggested bars from the passing sets. Copy into apps/ze-api/config/config.yaml"
        " under system_one.surfaces.routing, then enable system_one and the surface:"
    )
    for key, value in suggestion.items():
        print(
            f"  {key}: {value if value is not None else 'null  # no safe value on this set'}"
        )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dataset", type=Path, action="append", help="repeat for several sets"
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout-ms", type=int, default=10_000)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--seed", type=int, default=164)
    parser.add_argument(
        "--recall",
        action="store_true",
        help="offline E5 shortlist recall only; no OpenRouter call, no credits",
    )
    parser.add_argument(
        "--check-sets",
        action="store_true",
        help="offline: validate every routing set (schema, per-language counts); no network",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=None,
        help="shortlist size; defaults to system_one.surfaces.routing.shortlist_k",
    )
    args = parser.parse_args()
    if args.check_sets:
        raise SystemExit(check_sets())
    args.dataset = args.dataset or [DATASET]
    if args.k is None:
        block = (system_one_config().get("surfaces") or {}).get("routing") or {}
        args.k = block.get("shortlist_k", DEFAULT_SHORTLIST_K)
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
