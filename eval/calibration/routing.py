"""Opt-in live calibration for the routing System One surface (phase 164).

Calls the real System One endpoint over eval/calibration/routing.jsonl, costs
credits, and is never collected by pytest. Run it with `make calibrate-routing`.

Per row it builds the production shortlist with the local E5 singleton (the same
`judge.shortlist` helper as the router), asks the production questions with the
option order shuffled (eval only), then reports:

- Choice accuracy against the gold agent and a peakedness reliability table;
- `none` precision and recall;
- Noul separation for gold-mixed versus single rows;
- Score separation by complexity level;
- a grid of `choice_trust` x `multi_specialist_hold` with the 160 false compounds
  each pair would remove and the harmful trusts it would add;
- suggested values for `choice_trust`, `multi_specialist_hold` and
  `complexity_lookup_max`.

The wire Score is the expected level index (0 = lookup, 2 = multi_hop). The Score
table and the suggested `complexity_lookup_max` use it normalised to [0, 1], the
scale the bar is configured in.
"""

from __future__ import annotations

import argparse
import asyncio
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
from ze_core.openrouter.system_one import DEFAULT_MODEL, OpenRouterSystemOneClient
from ze_core.routing.judge import (
    DEFAULT_SHORTLIST_K,
    RoutingSurfaceConfig,
    build_questions,
    build_state,
    decide,
    normalise_complexity_score,
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
LEVELS = ["lookup", "single_tool", "multi_hop"]


@dataclass
class Row:
    id: str
    lang: str
    prompt: str
    gold_agent: str
    gold_multi: bool
    gold_complexity: str
    history: str | None = None


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
            gold_complexity=raw["gold_complexity"],
            history=raw.get("history"),
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


def load_roster() -> dict[str, str]:
    """Enabled agents and their descriptions from the checked-in agent modules."""
    from ze_agents.bootstrap import reload_agent_modules

    spec = importlib.util.spec_from_file_location(
        "_routing_agent_modules", AGENT_MODULES
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reload_agent_modules(module.ALL_AGENT_MODULE_PATHS)
    return {
        name: cls.description.strip()
        for name, cls in sorted(get_enabled_agents().items())
    }


def rank(embedder: Any, roster: dict[str, str], text: str) -> list[tuple[str, float]]:
    names = sorted(roster)
    matrix = embedder.encode_passage(
        [roster[n] for n in names], normalize_embeddings=True
    )
    vec = embedder.encode_query(text, normalize_embeddings=True)
    scores = (matrix @ vec).tolist()
    return sorted(zip(names, scores), key=lambda p: p[1], reverse=True)


RECALL_KS = (2, 3, 4, 5, 6)


def shortlist_recall(
    embedder: Any,
    roster: dict[str, str],
    rows: list[Row],
    ks: tuple[int, ...] = RECALL_KS,
) -> dict[int, list[Row]]:
    """Rows whose gold agent is outside the E5 top-k, per k. Offline: no System One call."""
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


def report_recall(
    embedder: Any,
    roster: dict[str, str],
    rows: list[Row],
    ks: tuple[int, ...] = RECALL_KS,
) -> None:
    scored = [r for r in rows if r.gold_agent in roster]
    misses = shortlist_recall(embedder, roster, rows, ks)
    print(
        f"\n== E5 shortlist recall of the gold agent ({len(scored)} rows with a gold agent)"
    )
    print("k     recall   missed")
    for k in ks:
        hit = len(scored) - len(misses[k])
        print(f"{k:<5d} {hit / len(scored):.3f}    {len(misses[k])}")
    worst = ks[0]
    by_agent: Counter[str] = Counter(r.gold_agent for r in misses[worst])
    print(f"missed at k={worst} by gold agent: {dict(by_agent)}")
    for row in misses[DEFAULT_SHORTLIST_K]:
        print(f"   k={DEFAULT_SHORTLIST_K} miss {row.id}: gold={row.gold_agent}")


def shuffled_questions(roster: dict[str, str], names: list[str], rng: random.Random):
    order = list(names)
    rng.shuffle(order)
    return build_questions({n: roster[n] for n in order})


async def run_rows(
    client: Any,
    embedder: Any,
    roster: dict[str, str],
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
            roster, names, random.Random(seed * 100003 + index)
        )
        state = build_state(row.prompt, row.history, None)
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


def report_reliability(outcomes: list[Outcome]) -> None:
    print("\n== Choice peakedness reliability")
    print("bin          n   mean_conf   accuracy")
    points = [
        (conf, choice == o.row.gold_agent)
        for o in single_rows(outcomes)
        for choice, conf in [predicted(o)]
        if conf is not None
    ]
    ece = 0.0
    for lo, hi in zip(BINS, BINS[1:]):
        bucket = [(c, ok) for c, ok in points if lo <= c < hi]
        if bucket:
            conf = sum(c for c, _ in bucket) / len(bucket)
            acc = sum(ok for _, ok in bucket) / len(bucket)
            ece += len(bucket) * abs(conf - acc)
            print(
                f"[{lo:.1f},{min(hi, 1.0):.1f})".ljust(11)
                + f"{len(bucket):4d}   {conf:8.3f}   {acc:8.3f}"
            )
    if points:
        print(f"ECE = {ece / len(points):.3f}")


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


def score_values(outcomes: list[Outcome]) -> dict[str, list[float]]:
    by_level: dict[str, list[float]] = {level: [] for level in LEVELS}
    for o in outcomes:
        answer = o.result.answers.get("complexity") if o.ok else None
        if answer is not None and answer.score is not None:
            score = normalise_complexity_score(answer.score)
            if score is not None:
                by_level[o.row.gold_complexity].append(score)
    return by_level


def suggest_lookup_max(by_level: dict[str, list[float]]) -> float | None:
    lookup = by_level["lookup"]
    rest = by_level["single_tool"] + by_level["multi_hop"]
    if not lookup or not rest:
        return None
    candidates = sorted({round(v, 2) for v in lookup + rest})
    best = max(
        candidates,
        key=lambda bar: sum(s <= bar for s in lookup) + sum(s > bar for s in rest),
    )
    return best


def report_score(outcomes: list[Outcome]) -> float | None:
    by_level = score_values(outcomes)
    print("\n== complexity Score by gold level (check it rises lookup -> multi_hop)")
    for level in LEVELS:
        values = by_level[level]
        if values:
            print(
                f"{level:12s} n={len(values):3d} mean={statistics.mean(values):.2f}"
                f" min={min(values):.2f} max={max(values):.2f}"
            )
    bar = suggest_lookup_max(by_level)
    if bar is not None:
        print(f"Suggested complexity_lookup_max: {bar}")
    return bar


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


def report(outcomes: list[Outcome]) -> dict[str, float | None]:
    report_accuracy(outcomes)
    report_reliability(outcomes)
    report_none(outcomes)
    report_noul(outcomes)
    lookup_max = report_score(outcomes)
    pair = report_grid(grid_metrics(outcomes))
    suggestion = {
        "choice_trust": pair[0] if pair else None,
        "multi_specialist_hold": pair[1] if pair else None,
        "complexity_lookup_max": lookup_max,
    }
    return suggestion


def system_one_config() -> dict:
    return (yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}).get(
        "system_one"
    ) or {}


async def main_async(args: argparse.Namespace) -> int:
    if args.recall:
        from ze_core.embeddings import get_embedder

        report_recall(get_embedder(), load_roster(), load_rows(args.dataset))
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
    roster = load_roster()
    rows = load_rows(args.dataset)
    print(
        f"model={client._model} rows={len(rows)} agents={len(roster)} k={args.k} seed={args.seed}"
    )
    outcomes = await run_rows(
        client,
        get_embedder(),
        roster,
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
    suggestion = report(outcomes)
    print(
        "\nCopy into apps/ze-api/config/config.yaml under system_one.surfaces.routing,"
        " then enable system_one and the surface:"
    )
    for key, value in suggestion.items():
        print(
            f"  {key}: {value if value is not None else 'null  # no safe value on this set'}"
        )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout-ms", type=int, default=10_000)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--seed", type=int, default=164)
    parser.add_argument(
        "--recall",
        action="store_true",
        help="offline E5 shortlist recall only; no OpenRouter call, no credits",
    )
    parser.add_argument("--k", type=int, default=DEFAULT_SHORTLIST_K)
    raise SystemExit(asyncio.run(main_async(parser.parse_args())))


if __name__ == "__main__":
    main()
