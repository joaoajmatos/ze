"""Opt-in live calibration for the speech-act System One surface (phase 163).

Calls the real System One endpoint over eval/calibration/speech_act.jsonl, costs
credits, and is never collected by pytest. Run it with `make calibrate-speech-act`.

It asks the production questions per row (option order shuffled, eval only), then
reports exact-act accuracy, a confusion matrix, a Choice-confidence reliability
table, fact precision/recall over a grid of hold bars, and suggested bars.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path

import yaml

from ze_agents.system_one import SystemOneQuestion, SystemOneResult
from ze_core.openrouter.system_one import DEFAULT_MODEL, OpenRouterSystemOneClient
from ze_memory.speech_act_judge import (
    SPEECH_ACT_QUESTIONS,
    SpeechActSurfaceConfig,
    build_state,
    decide,
)
from ze_memory.types import SpeechAct

ROOT = Path(__file__).resolve().parents[2]
DATASET = Path(__file__).with_name("speech_act.jsonl")
CONFIG = ROOT / "apps" / "ze-api" / "config" / "config.yaml"
GRID = [round(0.5 + 0.05 * i, 2) for i in range(10)]
BINS = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0001]
ACTS = [a.value for a in SpeechAct]


@dataclass
class Row:
    id: str
    lang: str
    user: str
    assistant: str
    gold_act: str
    gold_family: str
    gold_persist: bool


def load_rows(path: Path) -> list[Row]:
    rows: list[Row] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            raw = json.loads(line)
            rows.append(
                Row(
                    **{k: raw[k] for k in Row.__dataclass_fields__},
                )
            )
    ids = [r.id for r in rows]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate ids in calibration set")
    return rows


def shuffled_questions(rng: random.Random) -> dict[str, SystemOneQuestion]:
    questions = dict(SPEECH_ACT_QUESTIONS)
    for qid in ("speech_act", "family"):
        base = SPEECH_ACT_QUESTIONS[qid]
        keys = list(base.criteria)
        rng.shuffle(keys)
        questions[qid] = replace(base, criteria={k: base.criteria[k] for k in keys})
    return questions


def system_one_config() -> dict:
    return (yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}).get(
        "system_one"
    ) or {}


async def run_rows(
    client: OpenRouterSystemOneClient, rows: list[Row], seed: int, concurrency: int
) -> dict[str, SystemOneResult]:
    sem = asyncio.Semaphore(concurrency)

    async def one(index: int, row: Row) -> tuple[str, SystemOneResult]:
        questions = shuffled_questions(random.Random(seed * 100003 + index))
        async with sem:
            result = await client.evaluate(
                build_state(row.user, row.assistant), questions
            )
        return row.id, result

    return dict(await asyncio.gather(*(one(i, r) for i, r in enumerate(rows))))


def predicted_act(result: SystemOneResult) -> str | None:
    answer = result.answers.get("speech_act")
    return answer.choice if answer is not None else None


def report_accuracy(rows: list[Row], results: dict[str, SystemOneResult]) -> None:
    for lang in ("en", "pt"):
        scoped = [r for r in rows if r.lang == lang and results[r.id].outcome == "ok"]
        hits = sum(predicted_act(results[r.id]) == r.gold_act for r in scoped)
        print(
            f"\n== [{lang}] exact-act accuracy: {hits}/{len(scoped)}"
            f" = {hits / len(scoped):.3f}"
            if scoped
            else f"\n== [{lang}] no ok rows"
        )
        matrix: dict[str, Counter] = defaultdict(Counter)
        for r in scoped:
            matrix[r.gold_act][predicted_act(results[r.id]) or "none"] += 1
        header = "gold \\ pred".ljust(12) + "".join(a[:8].rjust(9) for a in ACTS)
        print(header)
        for gold in ACTS:
            if gold in matrix:
                print(
                    gold.ljust(12)
                    + "".join(str(matrix[gold][a]).rjust(9) for a in ACTS)
                )


def report_reliability(rows: list[Row], results: dict[str, SystemOneResult]) -> None:
    print("\n== speech_act Choice confidence reliability")
    print("bin          n   mean_conf   accuracy")
    ece = 0.0
    total = 0
    points = []
    for r in rows:
        res = results[r.id]
        answer = res.answers.get("speech_act") if res.outcome == "ok" else None
        if answer is not None and answer.confidence is not None:
            points.append((answer.confidence, answer.choice == r.gold_act))
    for lo, hi in zip(BINS, BINS[1:]):
        bucket = [(c, ok) for c, ok in points if lo <= c < hi]
        if not bucket:
            continue
        conf = sum(c for c, _ in bucket) / len(bucket)
        acc = sum(ok for _, ok in bucket) / len(bucket)
        ece += len(bucket) * abs(conf - acc)
        total += len(bucket)
        print(
            f"[{lo:.1f},{min(hi, 1.0):.1f})".ljust(11)
            + f"{len(bucket):4d}   {conf:8.3f}   {acc:8.3f}"
        )
    if total:
        print(f"ECE = {ece / total:.3f}")


def grid_metrics(rows: list[Row], results: dict[str, SystemOneResult]):
    scored = [r for r in rows if results[r.id].outcome == "ok"]
    gold_positive = sum(r.gold_persist for r in scored)
    out = []
    for choice in GRID:
        for bio in GRID:
            cfg = SpeechActSurfaceConfig(
                enabled=True, choice_hold=choice, biography_hold=bio
            )
            predicted = [decide(results[r.id], cfg).kind == "persist" for r in scored]
            tp = sum(p and r.gold_persist for p, r in zip(predicted, scored))
            fp = sum(p and not r.gold_persist for p, r in zip(predicted, scored))
            precision = tp / (tp + fp) if tp + fp else 1.0
            recall = tp / gold_positive if gold_positive else 0.0
            out.append((choice, bio, precision, recall, tp, fp))
    return out


def report_grid(metrics) -> tuple[float, float] | None:
    print("\n== fact precision / recall by bar (choice_hold rows, biography_hold cols)")
    print("choice\\bio ".ljust(11) + "".join(f"{b:>12.2f}" for b in GRID))
    by_pair = {(c, b): (p, r) for c, b, p, r, _, _ in metrics}
    for c in GRID:
        cells = "".join(
            f"{by_pair[(c, b)][0]:>7.2f}/{by_pair[(c, b)][1]:<4.2f}" for b in GRID
        )
        print(f"{c:>9.2f}  " + cells)
    safe = [m for m in metrics if m[2] == 1.0 and m[4] > 0]
    if not safe:
        print(
            "\nNo bar pair reaches fact precision 1.0 with any true positive on this set."
        )
        return None
    best = min(safe, key=lambda m: (m[0] + m[1], -m[3]))
    print(
        f"\nSuggested: choice_hold: {best[0]}  biography_hold: {best[1]}"
        f"  (precision 1.0, recall {best[3]:.2f}; lowest pair at precision 1.0)"
    )
    return best[0], best[1]


async def main_async(args: argparse.Namespace) -> int:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print(
            "OPENROUTER_API_KEY is required (this run is live and costs credits).",
            file=sys.stderr,
        )
        return 2
    config = system_one_config()
    client = OpenRouterSystemOneClient(
        api_key=api_key,
        model=args.model or config.get("model", DEFAULT_MODEL),
        timeout_ms=args.timeout_ms,
    )
    rows = load_rows(args.dataset)
    print(f"model={client._model} rows={len(rows)} seed={args.seed}")
    results = await run_rows(client, rows, args.seed, args.concurrency)
    skipped = Counter(r.skip_reason for r in results.values() if r.outcome == "skip")
    if skipped:
        print(f"skipped rows (excluded from metrics): {dict(skipped)}")
    if all(r.outcome == "skip" for r in results.values()):
        print("Every call was skipped; nothing to calibrate.", file=sys.stderr)
        return 1
    report_accuracy(rows, results)
    report_reliability(rows, results)
    report_grid_result = report_grid(grid_metrics(rows, results))
    if report_grid_result is None:
        return 0
    print(
        "\nCopy into apps/ze-api/config/config.yaml, then enable system_one and the surface."
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout-ms", type=int, default=10_000)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--seed", type=int, default=163)
    raise SystemExit(asyncio.run(main_async(parser.parse_args())))


if __name__ == "__main__":
    main()
