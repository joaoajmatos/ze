"""Calibration for the complexity (tier) System One surface (phase 182).

`make calibrate-complexity` calls the real System One endpoint with the `needs_deep_reasoning`
Noul over the tuned set (eval/calibration/complexity.jsonl). Each row's state is built by the
production `build_tier_state` over a synthetic `AgentState`/`AgentContext`, so the bar is the bar
production sees. It costs credits and is never collected by pytest.

- Default `--set tuned`: per language the Noul histogram by gold tier, false downgrades, light
  recall, precision, skipped share, latency, and the suggested `simple_max` (tuned set only).
- `--set holdout --simple-max X`: the single verdict run on eval/calibration/complexity_holdout.jsonl
  at the frozen bar. ENABLE or KEEP OFF per language with the failing clause. Tuning after this
  run voids the set (FR-019): write a new held-out file before the next verdict.
- `--check-sets`: offline. Schema and quotas only, no network. Prints counts, never row text.

Acceptance rule per language (FR-016): zero false downgrades, light recall >= 0.5, skipped or
invalid rows <= 10%.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

import yaml

from ze_agents.system_one import SystemOneResult
from ze_agents.types import AgentContext
from ze_core.orchestration.judgment_state import build_tier_state
from ze_core.orchestration.nodes.context import ResumeRecap
from ze_core.routing.tier import (
    Q_DEEP,
    ComplexitySurfaceConfig,
    build_tier_question,
    decide_tier,
)

ROOT = Path(__file__).resolve().parents[2]
TUNED = Path(__file__).with_name("complexity.jsonl")
HOLDOUT = Path(__file__).with_name("complexity_holdout.jsonl")
VERDICT_MARKER = ROOT / "eval" / "results" / "complexity_holdout_verdict.json"
CONFIG = ROOT / "apps" / "ze-api" / "config" / "config.yaml"

LANGS = ("en", "pt")
AGENTS = ("companion", "research", "goals")
TIERS = ("simple", "full")
KINDS = (
    "single",
    "multi_turn",
    "anaphoric",
    "resumed",
    "with_memory",
    "with_focus",
    "with_skill",
)
ROLES = ("user", "assistant")
MAX_MEMORY = 5
BAR_STEP = 0.05
RECALL_FLOOR = 0.5
SKIPPED_CEILING = 0.10
BINS = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0001]


@dataclass(frozen=True)
class Quota:
    """Minimum rows per language (holdout brief; tuned is the same shape, scaled)."""

    rows: int
    per_tier: int
    per_agent_tier: int
    conversation: int
    anaphoric: int
    anaphoric_per_tier: int
    per_context: int
    single: int


TUNED_QUOTA = Quota(40, 16, 2, 16, 6, 3, 2, 4)
HOLDOUT_QUOTA = Quota(24, 10, 2, 10, 6, 3, 2, 4)


@dataclass
class Row:
    id: str
    lang: str
    agent: str
    conversation: list[dict[str, str]]
    recap: str | None
    memory: list[str]
    focus: str | None
    skill: dict[str, str] | None
    prompt: str
    gold_tier: str
    kind: list[str]
    why: str = ""


@dataclass(frozen=True)
class Outcome:
    """One scored row. ``noul`` is ``None`` when the row was skipped or the answer invalid."""

    id: str
    lang: str
    agent: str
    gold_tier: str
    noul: float | None
    latency_ms: int = 0
    skip_reason: str | None = None


@dataclass
class LangVerdict:
    lang: str
    rows: int = 0
    simple_rows: int = 0
    full_rows: int = 0
    light: int = 0
    true_light: int = 0
    false_downgrades: int = 0
    skipped: int = 0
    failing: list[str] = field(default_factory=list)

    @property
    def recall(self) -> float:
        return self.true_light / self.simple_rows if self.simple_rows else 0.0

    @property
    def precision(self) -> float:
        return self.true_light / self.light if self.light else 1.0

    @property
    def skipped_share(self) -> float:
        return self.skipped / self.rows if self.rows else 1.0

    @property
    def enabled(self) -> bool:
        return not self.failing


@dataclass
class Verdict:
    per_lang: dict[str, LangVerdict]

    @property
    def enabled(self) -> bool:
        return all(self.per_lang[lang].enabled for lang in LANGS)


# --- loading and shape ---------------------------------------------------------------


def load_rows(path: Path) -> list[Row]:
    rows = []
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


def _row_problems(name: str, r: Row) -> list[str]:
    problems: list[str] = []
    where = f"{name}/{r.id}"
    if r.lang not in LANGS:
        problems.append(f"{where}: bad lang")
    if r.agent not in AGENTS:
        problems.append(f"{where}: bad agent")
    if r.gold_tier not in TIERS:
        problems.append(f"{where}: bad gold_tier")
    if not r.prompt.strip():
        problems.append(f"{where}: empty prompt")
    unknown = [k for k in r.kind if k not in KINDS]
    if unknown:
        problems.append(f"{where}: unknown kind tags {unknown}")
    if any(m.get("role") not in ROLES or not m.get("content") for m in r.conversation):
        problems.append(f"{where}: bad conversation turn")
    if len(r.memory) > MAX_MEMORY:
        problems.append(f"{where}: more than {MAX_MEMORY} memory items")
    if r.recap and r.conversation:
        problems.append(f"{where}: recap row has a conversation")
    context = bool(r.conversation or r.recap or r.memory or r.focus or r.skill)
    if "single" in r.kind and context:
        problems.append(f"{where}: single row has context")
    if "resumed" in r.kind and not r.recap:
        problems.append(f"{where}: resumed row has no recap")
    if "anaphoric" in r.kind and not r.conversation:
        problems.append(f"{where}: anaphoric row has no conversation")
    return problems


def shape_problems(rows: list[Row], name: str, quota: Quota) -> list[str]:
    """Schema and quotas. Messages carry ids and counts only, never row text."""
    problems: list[str] = []
    for r in rows:
        problems.extend(_row_problems(name, r))
    for lang in LANGS:
        s = [r for r in rows if r.lang == lang]
        where = f"{name}/{lang}"
        if len(s) < quota.rows:
            problems.append(f"{where}: {len(s)} rows, need >= {quota.rows}")
        for tier in TIERS:
            n = sum(r.gold_tier == tier for r in s)
            if n < quota.per_tier:
                problems.append(f"{where}: {n} {tier} rows, need >= {quota.per_tier}")
            for agent in AGENTS:
                n = sum(r.gold_tier == tier and r.agent == agent for r in s)
                if n < quota.per_agent_tier:
                    problems.append(
                        f"{where}/{agent}/{tier}: {n} rows, need >= {quota.per_agent_tier}"
                    )
        n = sum(bool(r.conversation) for r in s)
        if n < quota.conversation:
            problems.append(
                f"{where}: {n} conversation rows, need >= {quota.conversation}"
            )
        anaphoric = [r for r in s if "anaphoric" in r.kind]
        if len(anaphoric) < quota.anaphoric:
            problems.append(
                f"{where}: {len(anaphoric)} anaphoric rows, need >= {quota.anaphoric}"
            )
        for tier in TIERS:
            n = sum(r.gold_tier == tier for r in anaphoric)
            if n < quota.anaphoric_per_tier:
                problems.append(
                    f"{where}: {n} anaphoric {tier} rows, need >= {quota.anaphoric_per_tier}"
                )
        for label, has in (
            ("memory", lambda r: bool(r.memory)),
            ("focus", lambda r: bool(r.focus)),
            ("skill", lambda r: bool(r.skill)),
            ("recap", lambda r: bool(r.recap)),
        ):
            n = sum(has(r) for r in s)
            if n < quota.per_context:
                problems.append(
                    f"{where}: {n} {label} rows, need >= {quota.per_context}"
                )
        n = sum("single" in r.kind for r in s)
        if n < quota.single:
            problems.append(f"{where}: {n} single rows, need >= {quota.single}")
    return problems


def cross_problems(tuned: list[Row], holdout: list[Row]) -> list[str]:
    problems: list[str] = []
    ids = [r.id for r in tuned + holdout]
    if len(ids) != len(set(ids)):
        problems.append("ids repeat across tuned and holdout")
    held = {_norm(r.prompt) for r in holdout}
    for r in tuned:
        if _norm(r.prompt) in held:
            problems.append(f"tuned/{r.id}: prompt equals a held-out prompt")
    return problems


# --- pure scoring --------------------------------------------------------------------


def suggest_simple_max(outcomes: Sequence[Outcome]) -> float | None:
    """Research R8 / FR-017: the highest 0.05 step strictly below every ``full`` row's Noul.

    ``None`` when there is no ``full`` row to bound the bar, or no ``simple`` row lies at or
    below the bar (the classes overlap so that no safe bar gives any light-model recall).
    """
    full = [o.noul for o in outcomes if o.gold_tier == "full" and o.noul is not None]
    if not full:
        return None
    steps = math.floor(round(min(full) / BAR_STEP, 9) - 1e-9)
    bar = round(steps * BAR_STEP, 2)
    if bar < 0.0:
        return None
    if not any(
        o.gold_tier == "simple" and o.noul is not None and o.noul <= bar
        for o in outcomes
    ):
        return None
    return bar


def verdict(outcomes: Sequence[Outcome], simple_max: float) -> Verdict:
    """FR-016, per language: zero false downgrades, light recall >= 0.5, skipped <= 10%."""
    per_lang: dict[str, LangVerdict] = {}
    for lang in LANGS:
        rows = [o for o in outcomes if o.lang == lang]
        v = LangVerdict(lang=lang, rows=len(rows))
        for o in rows:
            v.simple_rows += o.gold_tier == "simple"
            v.full_rows += o.gold_tier == "full"
            if o.noul is None:
                v.skipped += 1
                continue
            if o.noul <= simple_max:
                v.light += 1
                if o.gold_tier == "simple":
                    v.true_light += 1
                else:
                    v.false_downgrades += 1
        if not rows:
            v.failing.append("no rows")
        if v.false_downgrades:
            v.failing.append(f"false downgrades {v.false_downgrades} != 0")
        if v.simple_rows and v.true_light * 2 < v.simple_rows:
            v.failing.append(f"light recall {v.recall:.3f} < {RECALL_FLOOR}")
        elif not v.simple_rows and rows:
            v.failing.append("no simple rows")
        if v.skipped * 10 > v.rows:
            v.failing.append(
                f"skipped or invalid {v.skipped_share:.3f} > {SKIPPED_CEILING}"
            )
        per_lang[lang] = v
    return Verdict(per_lang)


def outcome_for(row: Row, result: SystemOneResult) -> Outcome:
    """Validity is production's own: the Noul must parse the way ``decide_tier`` parses it."""
    decision = decide_tier(
        result, ComplexitySurfaceConfig(enabled=True, simple_max=1.0)
    )
    answer = result.answers.get(Q_DEEP)
    if decision.decided_by == "skip":
        reason, noul = result.skip_reason or "error", None
    elif decision.decided_by == "invalid_answer" or answer is None:
        reason, noul = "invalid_answer", None
    else:
        reason, noul = None, float(answer.noul)
    return Outcome(
        id=row.id,
        lang=row.lang,
        agent=row.agent,
        gold_tier=row.gold_tier,
        noul=noul,
        latency_ms=result.latency_ms,
        skip_reason=reason,
    )


def percentile(values: Sequence[int], q: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1)]


# --- state ---------------------------------------------------------------------------


def row_state(row: Row) -> dict[str, str]:
    """The production tier state for this row, built from a synthetic ``AgentState``."""
    recap = ResumeRecap(session_narrative=row.recap).render() if row.recap else None
    ctx = AgentContext(
        session_id="calibration",
        prompt=row.prompt,
        intent="reason",
        messages=[*row.conversation, {"role": "user", "content": row.prompt}],
        resume_recap=recap,
        active_skills=[SimpleNamespace(**row.skill)] if row.skill else [],
    )
    memory = SimpleNamespace(
        facts=[],
        episodes=[
            SimpleNamespace(summary=text, relevance_score=1.0 - i / 100)
            for i, text in enumerate(row.memory)
        ],
    )
    return build_tier_state(
        {
            "prompt": row.prompt,
            "image_caption": None,
            "agent_context": ctx,
            "memory_context": memory if row.memory else None,
            "routing_hints": row.focus,
        }
    )


# --- live run ------------------------------------------------------------------------


STATE_FIELDS = ("conversation", "recap", "memory", "focus", "skill")


async def run_system_one(
    client: Any, rows: list[Row], concurrency: int, without: Sequence[str] = ()
) -> dict[str, SystemOneResult]:
    sem = asyncio.Semaphore(concurrency)
    questions = build_tier_question()

    async def one(row: Row) -> tuple[str, SystemOneResult]:
        async with sem:
            try:
                state = {k: v for k, v in row_state(row).items() if k not in without}
                result = await client.evaluate(state, questions, max_attempts=1)
            except Exception:
                result = SystemOneResult(outcome="skip", skip_reason="error")
        return row.id, result

    return dict(await asyncio.gather(*(one(r) for r in rows)))


# --- reports -------------------------------------------------------------------------


def report_histogram(outcomes: Sequence[Outcome], lang: str) -> None:
    print(f"\n== Noul histogram by gold tier [{lang}]")
    print("bin           simple   full")
    scored = [o for o in outcomes if o.lang == lang and o.noul is not None]
    for lo, hi in zip(BINS, BINS[1:]):
        simple = sum(o.gold_tier == "simple" and lo <= o.noul < hi for o in scored)
        full = sum(o.gold_tier == "full" and lo <= o.noul < hi for o in scored)
        if simple or full:
            print(
                f"[{lo:.2f},{min(hi, 1.0):.2f})".ljust(14) + f"{simple:5d}  {full:5d}"
            )


def report_language(
    outcomes: Sequence[Outcome], v: LangVerdict, simple_max: float
) -> None:
    rows = [o for o in outcomes if o.lang == v.lang]
    latencies = [o.latency_ms for o in rows if o.skip_reason != "error"]
    print(f"\n== [{v.lang}] at simple_max={simple_max}")
    print(
        f"  rows={v.rows} simple={v.simple_rows} full={v.full_rows}"
        f" light={v.light} falseDowngrades={v.false_downgrades}"
        f" recall={v.recall:.3f} ({v.true_light}/{v.simple_rows})"
        f" precision={v.precision:.3f}"
    )
    skipped = Counter(o.skip_reason for o in rows if o.noul is None)
    print(
        f"  skipped/invalid={v.skipped} ({v.skipped_share:.3f})"
        f" {dict(skipped) if skipped else ''}"
    )
    print(
        f"  latency ms p50={percentile(latencies, 0.5)} p90={percentile(latencies, 0.9)}"
    )
    for agent in AGENTS:
        mine = [o for o in rows if o.agent == agent]
        light = sum(o.noul is not None and o.noul <= simple_max for o in mine)
        print(
            f"  {agent:<10s} rows={len(mine):3d}"
            f" simple={sum(o.gold_tier == 'simple' for o in mine):3d}"
            f" full={sum(o.gold_tier == 'full' for o in mine):3d} light={light:3d}"
        )


def report_errors(outcomes: Sequence[Outcome], simple_max: float) -> None:
    """Tuned set only: every false downgrade and every missed light row, with its Noul."""
    print("\n== tuned-set errors at the bar used (id, gold, noul)")
    for o in outcomes:
        if o.noul is None:
            print(f"  {o.id}: {o.gold_tier} skipped ({o.skip_reason})")
        elif o.gold_tier == "full" and o.noul <= simple_max:
            print(f"  {o.id}: full judged light  {o.noul:.3f}")
        elif o.gold_tier == "simple" and o.noul > simple_max:
            print(f"  {o.id}: simple kept full   {o.noul:.3f}")


# --- main ----------------------------------------------------------------------------


def report_borderline(
    outcomes: Sequence[Outcome], lo: float = 0.15, hi: float = 0.5
) -> None:
    """Tuned set only: every row whose Noul sits near the bar, to read the margin by eye."""
    print(
        f"\n== tuned-set borderline rows, Noul in [{lo}, {hi}) (noul, id, lang, agent, gold)"
    )
    near = sorted(
        (o for o in outcomes if o.noul is not None and lo <= o.noul < hi),
        key=lambda o: o.noul,
    )
    for o in near:
        print(f"  {o.noul:.3f}  {o.id} {o.lang} {o.agent:<9s} gold {o.gold_tier}")
    full = sorted(
        o.noul for o in outcomes if o.gold_tier == "full" and o.noul is not None
    )
    simple = sorted(
        o.noul for o in outcomes if o.gold_tier == "simple" and o.noul is not None
    )
    if full and simple:
        print(
            f"  lowest full {full[0]:.3f}, highest simple {simple[-1]:.3f},"
            f" median full {full[len(full) // 2]:.3f},"
            f" median simple {simple[len(simple) // 2]:.3f}"
        )


def config_system_one() -> dict:
    return (yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}).get(
        "system_one"
    ) or {}


def _counts(rows: list[Row], lang: str) -> str:
    s = [r for r in rows if r.lang == lang]
    cells = [f"{len(s)} rows"]
    for tier in TIERS:
        per_agent = {
            a: sum(r.gold_tier == tier and r.agent == a for r in s) for a in AGENTS
        }
        cells.append(f"{tier} {sum(per_agent.values())} {per_agent}")
    anaphoric = [r for r in s if "anaphoric" in r.kind]
    cells.append(
        f"conversation {sum(bool(r.conversation) for r in s)}"
        f" anaphoric {len(anaphoric)} (simple {sum(r.gold_tier == 'simple' for r in anaphoric)}"
        f" full {sum(r.gold_tier == 'full' for r in anaphoric)})"
        f" single {sum('single' in r.kind for r in s)}"
    )
    cells.append(
        f"memory {sum(bool(r.memory) for r in s)} focus {sum(bool(r.focus) for r in s)}"
        f" skill {sum(bool(r.skill) for r in s)} recap {sum(bool(r.recap) for r in s)}"
    )
    return f"  {lang}: " + "; ".join(cells)


def check_sets() -> int:
    sets: list[tuple[str, Path, Quota]] = [
        ("tuned", TUNED, TUNED_QUOTA),
        ("holdout", HOLDOUT, HOLDOUT_QUOTA),
    ]
    loaded: dict[str, list[Row]] = {}
    problems: list[str] = []
    for name, path, quota in sets:
        if not path.exists():
            print(f"{name}: {path.name} missing")
            problems.append(f"{name}: {path.name} does not exist")
            continue
        rows = load_rows(path)
        loaded[name] = rows
        print(f"{name}: {len(rows)} rows")
        for lang in LANGS:
            print(_counts(rows, lang))
        problems.extend(shape_problems(rows, name, quota))
    if len(loaded) == 2:
        problems.extend(cross_problems(loaded["tuned"], loaded["holdout"]))
    for p in problems:
        print("PROBLEM:", p, file=sys.stderr)
    return 1 if problems else 0


async def main_async(args: argparse.Namespace) -> int:
    if args.check_sets:
        return check_sets()
    holdout = args.set == "holdout"
    path = HOLDOUT if holdout else TUNED
    if not path.exists():
        print(f"{path.name} does not exist; run --check-sets.", file=sys.stderr)
        return 1
    if holdout and args.simple_max is None:
        print("--set holdout needs the frozen --simple-max.", file=sys.stderr)
        return 2
    if holdout and args.without:
        print(
            "--without is a tuning experiment; the verdict run uses the production state.",
            file=sys.stderr,
        )
        return 2
    if holdout and VERDICT_MARKER.exists() and not args.rerun:
        print(
            f"The held-out set was already scored once ({VERDICT_MARKER.name});"
            " it is spent for this bar (FR-019). Write a new held-out file, or pass --rerun.",
            file=sys.stderr,
        )
        return 2
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print(
            "OPENROUTER_API_KEY is required (this run is live and costs credits).",
            file=sys.stderr,
        )
        return 2
    rows = load_rows(path)
    tuned = load_rows(TUNED) if TUNED.exists() else []
    problems = shape_problems(rows, args.set, HOLDOUT_QUOTA if holdout else TUNED_QUOTA)
    if holdout and tuned:
        problems += cross_problems(tuned, rows)
    if problems:
        print("Dataset problems; run --check-sets.", file=sys.stderr)
        return 1
    if holdout:
        print(
            "WARNING: held-out verdict run. Changing wording or the bar after this run voids"
            " the set; write a fresh held-out file before the next verdict (FR-019)."
        )

    from ze_core.openrouter.system_one import DEFAULT_MODEL, OpenRouterSystemOneClient

    settings = config_system_one()
    model = args.model or settings.get("model") or DEFAULT_MODEL
    timeout_ms = args.timeout_ms or int(settings.get("timeout_ms", 2000))
    client = OpenRouterSystemOneClient(
        api_key=api_key, model=model, timeout_ms=timeout_ms
    )
    print(f"model={model} set={args.set} rows={len(rows)} timeout_ms={timeout_ms}")
    started = time.monotonic()
    results = await run_system_one(client, rows, args.concurrency, args.without)
    outcomes = [outcome_for(r, results[r.id]) for r in rows]
    print(f"live run took {time.monotonic() - started:.1f}s")

    if not holdout:
        suggestion = suggest_simple_max(outcomes)
        bar = args.simple_max if args.simple_max is not None else suggestion
        for lang in LANGS:
            report_histogram(outcomes, lang)
        if bar is None:
            print(
                "\nNo safe bar: the classes overlap, so no simple_max gives any light recall."
            )
            return 0
        v = verdict(outcomes, bar)
        for lang in LANGS:
            report_language(outcomes, v.per_lang[lang], bar)
        report_errors(outcomes, bar)
        report_borderline(outcomes)
        print(f"\nSuggested simple_max (tuned set only): {suggestion}\nbar used: {bar}")
        return 0

    bar = args.simple_max
    v = verdict(outcomes, bar)
    for lang in LANGS:
        report_histogram(outcomes, lang)
        report_language(outcomes, v.per_lang[lang], bar)
    print("\n== HELD-OUT VERDICT")
    print(f"simple_max: {bar}")
    for lang in LANGS:
        lv = v.per_lang[lang]
        print(
            f"[{lang}] {'ENABLE' if lv.enabled else 'KEEP OFF'}"
            f"  falseDowngrades={lv.false_downgrades} recall={lv.recall:.3f}"
            f" ({lv.true_light}/{lv.simple_rows}) skipped={lv.skipped_share:.3f}"
            f" precision={lv.precision:.3f}"
            + (f"\n      failing: {'; '.join(lv.failing)}" if lv.failing else "")
        )
    print(f"OVERALL: {'ENABLE' if v.enabled else 'KEEP OFF'}")
    VERDICT_MARKER.parent.mkdir(parents=True, exist_ok=True)
    VERDICT_MARKER.write_text(
        json.dumps({"simple_max": bar, "overall": v.enabled, "at": time.time()}),
        encoding="utf-8",
    )
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--check-sets", action="store_true", help="offline schema and quota check"
    )
    p.add_argument("--set", choices=("tuned", "holdout"), default="tuned")
    p.add_argument(
        "--simple-max",
        type=float,
        default=None,
        help="the bar (required and frozen for --set holdout; overrides the suggestion on tuned)",
    )
    p.add_argument("--model", default=None)
    p.add_argument(
        "--timeout-ms",
        type=int,
        default=None,
        help="default: system_one.timeout_ms from config.yaml, so the skip rate matches production",
    )
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument(
        "--without",
        nargs="*",
        choices=STATE_FIELDS,
        default=[],
        help="tuned-set experiment: drop these state fields before the request",
    )
    p.add_argument(
        "--rerun",
        action="store_true",
        help="score the held-out set again after a failed run",
    )
    return p


def main() -> None:
    args = parser().parse_args()
    if args.simple_max is not None and not 0.0 <= args.simple_max <= 1.0:
        raise SystemExit("--simple-max must be within [0, 1]")
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
