"""Shared plumbing of the System One calibration runners (phase 202).

Each runner keeps its own rows, quotas, scoring, baselines and acceptance rule. This module holds
what they all repeated: loading rows, the production surface config, the live run, reliability and
grid tables, saved results and the shared command-line flags. Runners import it as a sibling
(`sys.path.insert(0, str(Path(__file__).resolve().parent))`, then `import harness`).
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import statistics
import sys
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, TypeVar

import yaml
from ze_agents.judgment import SurfaceConfig
from ze_agents.system_one import (
    SystemOneAnswer,
    SystemOneClient,
    SystemOneQuestion,
    SystemOneResult,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "apps" / "ze-api" / "config" / "config.yaml"
LANGS = ("en", "pt")
GRID = [round(0.5 + 0.05 * i, 2) for i in range(10)]
CONFIDENCE_EDGES = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0001]
NOUL_EDGES = [0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0001]

R = TypeVar("R")
C = TypeVar("C", bound=SurfaceConfig)
M = TypeVar("M")


# --- rows ----------------------------------------------------------------------------


def load_jsonl(path: Path, make_row: Callable[[dict], R]) -> list[R]:
    rows = [
        make_row(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len({r.id for r in rows}) != len(rows):
        raise SystemExit(f"duplicate ids in {path.name}")
    return rows


def row_loader(cls: type[R]) -> Callable[[Path], list[R]]:
    """A loader for a row dataclass: every field the file carries, the rest by default."""
    fields = cls.__dataclass_fields__
    return lambda path: load_jsonl(
        path, lambda raw: cls(**{k: raw[k] for k in fields if k in raw})
    )


def norm(text: str) -> str:
    return " ".join(text.casefold().split())


def blind_overlap(a: Iterable[str], b: Iterable[str]) -> set[str]:
    return {norm(x) for x in a} & {norm(x) for x in b}


def overlap_problems(
    name: str, rows: Sequence, against: Sequence, *, field: str = "text", label: str | None = None
) -> list[str]:
    """Rows of ``rows`` whose ``field`` text also appears in ``against``."""
    shared = blind_overlap(
        (getattr(r, field) for r in rows), (getattr(r, field) for r in against)
    )
    label = label or f"a held-out {field}"
    return [
        f"{name}/{r.id}: {field} equals {label}"
        for r in rows
        if norm(getattr(r, field)) in shared
    ]


def split_problems(tuned: Sequence, holdout: Sequence, *, field: str = "text") -> list[str]:
    ids = [r.id for r in (*tuned, *holdout)]
    problems = ["ids repeat across tuned and holdout"] if len(ids) != len(set(ids)) else []
    return problems + overlap_problems("tuned", tuned, holdout, field=field)


def min_rows_problems(name: str, rows: Sequence, minimum: int) -> list[str]:
    counts = Counter(r.lang for r in rows)
    return [
        f"{name}/{lang}: {counts[lang]} rows, need >= {minimum}"
        for lang in LANGS
        if counts[lang] < minimum
    ]


def shape_report(problems: Sequence[str]) -> int:
    for problem in problems:
        print("PROBLEM:", problem, file=sys.stderr)
    return 1 if problems else 0


# --- production config ---------------------------------------------------------------


def load_config(path: Path = CONFIG) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def system_one_config() -> dict:
    return load_config().get("system_one") or {}


def surface_config(cls: type[C], *, enabled: bool = True, **bars: float | None) -> C:
    """A surface config built by the production parser, so a bad bar is as invalid here as there."""
    block = {"enabled": enabled, **bars}
    return cls.from_settings({"system_one": {"surfaces": {cls.SURFACE: block}}})


def configured(cls: type[C]) -> C:
    return cls.from_settings(load_config())


def parse_bar_list(text: str, names: Sequence[str]) -> dict[str, float]:
    try:
        values = [float(x) for x in text.split(",")]
        if len(values) != len(names):
            raise ValueError
    except ValueError:
        raise SystemExit(f"--bars needs {','.join(n.upper() for n in names)}") from None
    return dict(zip(names, values))


def bars_config(cls: type[C], text: str, names: Sequence[str]) -> C:
    cfg = surface_config(cls, **parse_bar_list(text, names))
    if not cfg.calibrated:
        raise SystemExit(f"--bars {text} is not a valid {cls.SURFACE} bar set")
    return cfg


# --- live run and saved results ------------------------------------------------------


def client_settings(args: argparse.Namespace) -> tuple[str, int]:
    from ze_core.openrouter.system_one import DEFAULT_MODEL

    settings = system_one_config()
    model = args.model or settings.get("model") or DEFAULT_MODEL
    return model, args.timeout_ms or int(settings.get("timeout_ms", 2000))


def api_key() -> str | None:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        print(
            "OPENROUTER_API_KEY is required (this run is live and costs credits).",
            file=sys.stderr,
        )
    return key or None


def make_client(args: argparse.Namespace) -> SystemOneClient | None:
    if (key := api_key()) is None:
        return None
    from ze_core.openrouter.system_one import OpenRouterSystemOneClient

    model, timeout_ms = client_settings(args)
    return OpenRouterSystemOneClient(api_key=key, model=model, timeout_ms=timeout_ms)


async def bounded(
    rows: Sequence[R], one: Callable[[int, R], Awaitable[M]], concurrency: int
) -> list[M]:
    sem = asyncio.Semaphore(concurrency)

    async def run(index: int, row: R) -> M:
        async with sem:
            return await one(index, row)

    return list(await asyncio.gather(*(run(i, r) for i, r in enumerate(rows))))


async def run_live(
    client: SystemOneClient,
    rows: Sequence[R],
    state_of: Callable[[R], str | dict],
    questions_of: Callable[[int, R], Mapping[str, SystemOneQuestion]],
    concurrency: int,
) -> dict[str, SystemOneResult]:
    """One single-attempt request per row, as production asks. A raised call is a skip."""

    async def one(index: int, row: R) -> SystemOneResult:
        try:
            return await client.evaluate(
                state_of(row), dict(questions_of(index, row)), max_attempts=1
            )
        except Exception:
            return SystemOneResult(outcome="skip", skip_reason="error")

    results = await bounded(rows, one, concurrency)
    return {r.id: result for r, result in zip(rows, results)}


def _result_from_dict(raw: dict) -> SystemOneResult:
    answers = {k: SystemOneAnswer(**v) for k, v in raw.get("answers", {}).items()}
    return SystemOneResult(**{**raw, "answers": answers})


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return {k: _plain(v) for k, v in value.items()}


def save_results(path: Path, results: Mapping[str, Any]) -> None:
    """``{id: result}`` or ``{id: {name: result}}`` (results may sit in a dataclass)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({k: _plain(v) for k, v in results.items()}), encoding="utf-8"
    )


def load_results(path: Path) -> dict[str, Any]:
    """The inverse of ``save_results``; a nested value comes back as ``{name: result}``."""

    def revive(raw: dict) -> Any:
        if "outcome" in raw:
            return _result_from_dict(raw)
        return {k: revive(v) for k, v in raw.items()}

    return {k: revive(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}


async def collect(
    args: argparse.Namespace,
    rows: Sequence[R],
    state_of: Callable[[R], str | dict],
    questions_of: Callable[[int, R], Mapping[str, SystemOneQuestion]],
    banner: Callable[[str], str],
) -> dict[str, SystemOneResult] | None:
    """Results from ``--load``, else a live run (saved to ``--save``); ``None`` without a key."""
    if args.load:
        print(f"results loaded from {args.load}")
        return load_results(args.load)
    client = make_client(args)
    if client is None:
        return None
    print(banner(client._model))
    results = await run_live(client, rows, state_of, questions_of, args.concurrency)
    if args.save:
        save_results(args.save, results)
    return results


# --- reports -------------------------------------------------------------------------


@dataclass(frozen=True)
class Bin:
    lo: float
    hi: float
    n: int
    mean: float
    rate: float


def reliability_bins(
    points: Iterable[tuple[float, bool]], edges: Sequence[float] = CONFIDENCE_EDGES
) -> list[Bin]:
    points = list(points)
    bins = []
    for lo, hi in zip(edges, edges[1:]):
        bucket = [(v, hit) for v, hit in points if lo <= v < hi]
        if bucket:
            bins.append(
                Bin(
                    lo,
                    hi,
                    len(bucket),
                    sum(v for v, _ in bucket) / len(bucket),
                    sum(hit for _, hit in bucket) / len(bucket),
                )
            )
    return bins


def ece(bins: Sequence[Bin]) -> float | None:
    total = sum(b.n for b in bins)
    return sum(b.n * abs(b.mean - b.rate) for b in bins) / total if total else None


def print_reliability(
    title: str,
    bins: Sequence[Bin],
    mean_label: str,
    rate_label: str,
    *,
    mean_width: int = 8,
    show_ece: bool = False,
) -> None:
    print(f"\n== {title}")
    print(f"bin          n   {mean_label}   {rate_label}")
    for b in bins:
        label = f"[{b.lo:.1f},{min(b.hi, 1.0):.1f})".ljust(11)
        print(f"{label}{b.n:4d}   {b.mean:{mean_width}.3f}   {b.rate:8.3f}")
    if show_ece and (value := ece(bins)) is not None:
        print(f"ECE = {value:.3f}")


def print_none_report(pairs: Iterable[tuple[str | None, str]], none: str = "none") -> None:
    """Precision and recall of the ``none`` answer over ``(predicted, gold)`` pairs."""
    pairs = list(pairs)
    tp = sum(p == none and g == none for p, g in pairs)
    fp = sum(p == none and g != none for p, g in pairs)
    fn = sum(p != none and g == none for p, g in pairs)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    print(f"\n== none: precision {precision:.2f} recall {recall:.2f} (tp={tp} fp={fp} fn={fn})")


def print_noul_stats(title: str, groups: Mapping[str, Sequence[float]]) -> None:
    print(f"\n== {title}")
    for label, values in groups.items():
        if values:
            print(
                f"{label:12s} n={len(values):3d} mean={statistics.mean(values):.2f}"
                f" min={min(values):.2f} max={max(values):.2f}"
            )


def bar_grid(
    axes: Mapping[str, Sequence[float]], metric: Callable[[dict[str, float]], M]
) -> list[tuple[dict[str, float], M]]:
    """``metric`` over every combination of the named bar axes."""
    names = list(axes)
    return [
        (bars, metric(bars))
        for values in itertools.product(*axes.values())
        for bars in [dict(zip(names, values))]
    ]


def print_grid(
    title: str,
    corner: str,
    grid: Sequence[tuple[dict[str, float], M]],
    rows: str,
    cols: str,
    cell: Callable[[M], str],
    *,
    width: int,
    label_width: int = 9,
    gap: int = 2,
    skip: Callable[[float, float], bool] = lambda r, c: False,
) -> None:
    by_pair = {(bars[rows], bars[cols]): m for bars, m in grid}
    row_axis = list(dict.fromkeys(r for r, _ in by_pair))
    col_axis = list(dict.fromkeys(c for _, c in by_pair))
    print(f"\n== {title}")
    print(corner + "".join(f"{c:>{width}.2f}" for c in col_axis))
    for r in row_axis:
        cells = "".join(
            f"{'-':>{width}s}" if skip(r, c) else cell(by_pair[(r, c)]) for c in col_axis
        )
        print(f"{r:>{label_width}.2f}{' ' * gap}{cells}")


def print_verdict(
    by_language: Mapping[str, tuple[bool, Sequence[str], str]], *, lead: Sequence[str] = ()
) -> bool:
    """``{lang: (passed, failing clauses, detail)}`` as ENABLE or KEEP OFF, then OVERALL."""
    print("\n== HELD-OUT VERDICT")
    for line in lead:
        print(line)
    for lang, (ok, failing, detail) in by_language.items():
        print(
            f"[{lang}] {'ENABLE' if ok else 'KEEP OFF'}  {detail}"
            + (f"\n      failing: {'; '.join(failing)}" if failing else "")
        )
    overall = all(ok for ok, _, _ in by_language.values())
    print(f"OVERALL: {'ENABLE' if overall else 'KEEP OFF'}")
    return overall


def held_out_warning(fr: str, what: str = "bars") -> None:
    print(
        f"WARNING: held-out verdict run. Changing wording or {what} after this run voids the"
        f" set; write a fresh held-out file before the next verdict ({fr})."
    )


# --- command line --------------------------------------------------------------------


def common_args(
    p: argparse.ArgumentParser,
    *,
    sets: Sequence[str] = (),
    bars: str | None = None,
    seed: int | None = None,
    timeout_ms: int | None = 10_000,
    check_sets: bool = True,
    load_flags: Sequence[str] = ("--load",),
) -> None:
    """The flags every System One runner shares; a runner adds its own beside them."""
    if check_sets:
        p.add_argument("--check-sets", action="store_true", help="offline dataset shape check")
    if sets:
        p.add_argument("--set", choices=sets, default=sets[0])
    if bars:
        p.add_argument("--bars", default=None, help=bars)
    p.add_argument("--model", default=None)
    p.add_argument(
        "--timeout-ms",
        type=int,
        default=timeout_ms,
        help=None if timeout_ms else "default: system_one.timeout_ms from config.yaml",
    )
    p.add_argument("--concurrency", type=int, default=4)
    if seed is not None:
        p.add_argument("--seed", type=int, default=seed)
    p.add_argument("--save", type=Path, default=None, help="store the raw results as JSON")
    p.add_argument(
        "--load",
        *load_flags[1:],
        dest="load",
        type=Path,
        default=None,
        help="report from saved results; no System One call",
    )
