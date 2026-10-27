"""Calibration for the commitment-intake System One surface (phase 173).

`make calibrate-commitment-intake` calls the real System One endpoint over the tuned set
(eval/calibration/commitment_intake.jsonl) and, on the same rows, replays the old two-surface
pipeline (163 speech-act request + 168 loop-gate request, frozen in commitment_intake_baseline.py)
as the baseline. It costs credits and is never collected by pytest.

- Default `--set tuned`: per language Choice accuracy, per-label precision and recall, duplicate
  bookings, false loop creates, fact and loop precision and recall, a reliability table per
  question, bar grids and suggested bars chosen on the tuned set only. Held-out rows are never
  read or printed. `--save PATH` stores the raw results so `--replay PATH` can re-tune bars
  offline without spending again.
- `--set holdout --bars CHOICE,FAMILY,BIOGRAPHY,LOOP,EXPLICIT,RESOLVES`: the single verdict run on
  eval/calibration/commitment_intake_holdout.jsonl with frozen wording and bars. ENABLE or KEEP OFF
  per language, with the failing clause. Tuning after this run voids the set (FR-020): write a new
  held-out file before the next verdict. `--replay` is refused on the held-out set.
- `--check-sets`: offline. Dataset shape only, no network.

Acceptance rule per language (FR-022): zero duplicate bookings, zero false loop creates, fact
precision >= baseline and fact recall >= baseline - 0.05, loop precision >= baseline and loop
recall >= baseline - 0.05, false resolves <= baseline, waiting_on rows write nothing, Choice accuracy >= 0.9. Choice accuracy
covers rows where the turn created nothing and that are not resolves rows; link accuracy
(outcome is a link of the right kind) covers the created-something rows and is reported beside
it (amendments of FR-022, 2026-10-16).
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness  # noqa: E402
from commitment_intake_baseline import (  # noqa: E402
    decide_baseline,
    questions_168,
    shuffled_163,
    state_163,
    state_168,
)
from ze_agents.nested_tools import TurnCreation  # noqa: E402
from ze_agents.system_one import SystemOneQuestion, SystemOneResult  # noqa: E402
from ze_worldstate.commitment_judge import (  # noqa: E402
    COMMITMENT_QUESTIONS,
    Q_COMMITMENT,
    CommitmentIntakeSurfaceConfig,
    IntakeOutcome,
    build_state,
    decide,
)

TUNED = Path(__file__).with_name("commitment_intake.jsonl")
HOLDOUT = Path(__file__).with_name("commitment_intake_holdout.jsonl")
HOLDOUT2 = Path(__file__).with_name("commitment_intake_holdout2.jsonl")
HOLDOUT3 = Path(__file__).with_name("commitment_intake_holdout3.jsonl")
LANGS = harness.LANGS
SPENT_SETS = ("holdout", "holdout2", "holdout3")
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
MIN_HOLDOUT_FACT_PER_LANG = 15
MIN_HOLDOUT_LOOP_PER_LANG = 15
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
GRID = harness.GRID
BAR_NAMES = (
    "choice_hold",
    "family_hold",
    "biography_hold",
    "loop_hold",
    "explicit_hold",
    "resolves_hold",
)
RECALL_SLACK = 0.05
MIN_CHOICE_ACCURACY = 0.9
CREATES = ("create_loop_declared", "create_loop_suspected")
WRITES = ("persist_fact", "resolve_loop", "link", *CREATES)
Q_FAMILY = "family"
Q_BIOGRAPHY = "biography"
Q_CONCERN = "is_open_concern"
Q_EXPLICIT = "explicit_declaration"
Q_RESOLVES = "resolves_existing"
SHUFFLED = (Q_COMMITMENT, Q_FAMILY)


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
    also_loop: bool = False

    @property
    def gold_fact(self) -> bool:
        return self.gold_choice == "fact"

    @property
    def gold_loop(self) -> bool:
        """A loop is the right outcome: a loop concern that the turn did not already book."""
        return (
            self.gold_choice == "loop"
            and self.turn_created == "none"
            and not self.gold_resolves
        )

    @property
    def created(self) -> TurnCreation:
        return TurnCreation(
            reminder_id="rem-1" if self.turn_created == "reminder" else None,
            goal_id="goal-1" if self.turn_created == "goal" else None,
        )


load_rows = harness.row_loader(Row)


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
        if r.also_loop and (r.kind != MIXED_KIND or r.gold_choice == "loop"):
            problems.append(
                f"{name}/{r.id}: also_loop is for mixed rows whose gold is not loop"
            )
        if r.also_loop and r.turn_created != "none":
            problems.append(f"{name}/{r.id}: also_loop with a created reminder or goal")
    return problems


def set_problems(
    name: str, rows: list[Row], minimum: int, *, require_kinds: bool = True
) -> list[str]:
    problems = row_problems(name, rows) + harness.min_rows_problems(name, rows, minimum)
    for lang in LANGS:
        scoped = [r for r in rows if r.lang == lang]
        for choice in CHOICES:
            if not any(r.gold_choice == choice for r in scoped):
                problems.append(f"{name}/{lang}: no row with choice {choice}")
        for created in CREATED:
            if not any(r.turn_created == created for r in scoped):
                problems.append(f"{name}/{lang}: no row with turn_created {created}")
        if require_kinds:
            for kind in (*HARD_NEGATIVE_KINDS, MIXED_KIND):
                if not any(r.kind == kind for r in scoped):
                    problems.append(f"{name}/{lang}: no {kind} row")
        if not any(r.gold_resolves for r in scoped):
            problems.append(f"{name}/{lang}: no resolves row")
    return problems


def kind_notes(name: str, rows: list[Row]) -> list[str]:
    """Hard-negative kind names a blind author may have spelled differently: notes, not problems."""
    notes: list[str] = []
    for lang in LANGS:
        scoped = [r for r in rows if r.lang == lang]
        for kind in (*HARD_NEGATIVE_KINDS, MIXED_KIND):
            if not any(r.kind == kind for r in scoped):
                notes.append(f"{name}/{lang}: no row with kind {kind}")
    return notes


def holdout_depth_problems(rows: list[Row], name: str = "holdout") -> list[str]:
    """FR-019: enough fact rows and gold-loop rows per language for the FR-022 comparisons."""
    problems: list[str] = []
    for lang in LANGS:
        scoped = [r for r in rows if r.lang == lang]
        facts = sum(r.gold_fact for r in scoped)
        loops = sum(r.gold_loop for r in scoped)
        if facts < MIN_HOLDOUT_FACT_PER_LANG:
            problems.append(
                f"{name}/{lang}: {facts} fact rows, need >= {MIN_HOLDOUT_FACT_PER_LANG}"
            )
        if loops < MIN_HOLDOUT_LOOP_PER_LANG:
            problems.append(
                f"{name}/{lang}: {loops} gold-loop rows, need >= {MIN_HOLDOUT_LOOP_PER_LANG}"
            )
    return problems


def _blind_problems(name: str, rows: list[Row], others: list[Row]) -> list[str]:
    problems = set_problems(name, rows, MIN_HOLDOUT_PER_LANG, require_kinds=False)
    problems += holdout_depth_problems(rows, name)
    if len({r.id for r in [*others, *rows]}) != len(others) + len(rows):
        problems.append(f"ids repeat between {name} and the other sets")
    return problems + harness.overlap_problems(
        name, rows, others, label="a tuned or earlier held-out text"
    )


def shape_problems(
    tuned: list[Row] | None,
    holdout: list[Row],
    holdout2: list[Row] | None = None,
    holdout3: list[Row] | None = None,
) -> list[str]:
    """`holdout`, `holdout2` and `holdout3` are spent (verdicts 2026-10-16), kept loadable for
    reference. Blind sets need not use our hard-negative kind names."""
    problems = set_problems("holdout", holdout, MIN_HOLDOUT_PER_LANG)
    problems += holdout_depth_problems(holdout)
    if tuned is not None:
        problems += set_problems("tuned", tuned, MIN_TUNED_PER_LANG)
        problems += harness.split_problems(tuned, holdout)
    earlier = [*holdout, *(tuned or [])]
    if holdout2 is not None:
        problems += _blind_problems("holdout2", holdout2, earlier)
        earlier = [*earlier, *holdout2]
    if holdout3 is not None:
        problems += _blind_problems("holdout3", holdout3, earlier)
    return problems


def check_sets() -> int:
    holdout = load_rows(HOLDOUT)
    tuned = load_rows(TUNED) if TUNED.exists() else None
    holdout2 = load_rows(HOLDOUT2) if HOLDOUT2.exists() else None
    holdout3 = load_rows(HOLDOUT3) if HOLDOUT3.exists() else None
    print(f"holdout (spent, reference only): {len(holdout)} rows")
    print(
        f"holdout2 (spent, reference only): {len(holdout2)} rows"
        if holdout2
        else "holdout2: not written yet"
    )
    print(
        f"holdout3: {len(holdout3)} rows" if holdout3 else "holdout3: not written yet"
    )
    print(f"tuned: {len(tuned)} rows" if tuned else "tuned: not written yet")
    problems = shape_problems(tuned, holdout, holdout2, holdout3)
    for name, rows in (("holdout2", holdout2), ("holdout3", holdout3)):
        for n in kind_notes(name, rows) if rows else []:
            print(f"NOTE {n}")
    return harness.shape_report(problems)


# --- predictions and scoring ---------------------------------------------------------


@dataclass(frozen=True)
class Pred:
    """What one pipeline did with one row, reduced to the facts the metrics read."""

    fact: bool = False
    create: bool = False
    declared: bool = False
    resolve: bool = False
    fallback: bool = False
    wrote: bool = False
    link_kind: str | None = None


def pred_from_outcome(outcome: IntakeOutcome) -> Pred:
    return Pred(
        fact=outcome.kind == "persist_fact",
        create=outcome.kind in CREATES,
        declared=outcome.kind == "create_loop_declared",
        resolve=outcome.kind == "resolve_loop",
        fallback=outcome.kind == "fallback",
        wrote=outcome.kind in WRITES,
        link_kind=outcome.link_kind if outcome.kind == "link" else None,
    )


def pred_from_baseline(fact: str, loop: str) -> Pred:
    create = loop in ("create_declared", "create_suspected")
    resolve = loop == "resolve"
    persist = fact == "persist"
    return Pred(
        fact=persist,
        create=create,
        declared=loop == "create_declared",
        resolve=resolve,
        fallback=fact == "fallback" and loop == "fallback",
        wrote=persist or create or resolve,
    )


@dataclass
class Counts:
    n: int = 0
    fallback: int = 0
    fact_pos: int = 0
    fact_hits: int = 0
    fact_pred: int = 0
    loop_pos: int = 0
    loop_hits: int = 0
    loop_pred: int = 0
    duplicates: int = 0
    false_creates: int = 0
    false_resolve: int = 0
    false_declared: int = 0
    explicit_total: int = 0
    explicit_ok: int = 0
    resolves_ok: int = 0
    waiting_total: int = 0
    waiting_written: int = 0
    choice_total: int = 0
    choice_ok: int = 0
    link_total: int = 0
    link_ok: int = 0

    @property
    def fact_precision(self) -> float:
        return self.fact_hits / self.fact_pred if self.fact_pred else 1.0

    @property
    def fact_recall(self) -> float:
        return self.fact_hits / self.fact_pos if self.fact_pos else 0.0

    @property
    def loop_precision(self) -> float:
        return self.loop_hits / self.loop_pred if self.loop_pred else 1.0

    @property
    def loop_recall(self) -> float:
        return self.loop_hits / self.loop_pos if self.loop_pos else 0.0

    @property
    def explicit_acc(self) -> float:
        return self.explicit_ok / self.explicit_total if self.explicit_total else 1.0

    @property
    def resolves_acc(self) -> float:
        return self.resolves_ok / self.n if self.n else 1.0

    @property
    def choice_acc(self) -> float:
        return self.choice_ok / self.choice_total if self.choice_total else 0.0

    @property
    def link_acc(self) -> float:
        return self.link_ok / self.link_total if self.link_total else 1.0


def predicted_choice(result: SystemOneResult) -> str | None:
    answer = result.answers.get(Q_COMMITMENT) if result.outcome == "ok" else None
    if answer is None or answer.choice is None:
        return None
    return str(answer.choice).strip().lower()


def score(
    rows: list[Row],
    preds: dict[str, Pred],
    choices: dict[str, str | None] | None = None,
) -> Counts:
    """A fallback row counts as a miss and never as a write. A skipped Choice counts as wrong.

    A mixed row with `also_loop` also carries a real open concern: a loop create or a loop Choice
    is acceptable there (neither a false create nor a required hit), and the row leaves the fact
    recall denominator when the pipeline answered with the loop.

    Choice accuracy covers rows where the turn created nothing and that are not resolves rows:
    the resolves clause judges those outcomes and the Choice question has no resolves option
    (amendment of 2026-10-16 after the holdout2 verdict, effective for the next verdict only).
    When a reminder or goal already exists the outcome is a link whatever the Choice says
    (decision row 5), so those rows are scored by `link_acc` instead (amendment of FR-022,
    2026-10-16)."""
    c = Counts()
    for r in rows:
        p = preds[r.id]
        c.n += 1
        c.fallback += p.fallback
        accepted_loop = r.also_loop and p.create
        c.fact_pos += r.gold_fact and not accepted_loop
        c.fact_pred += p.fact
        c.fact_hits += p.fact and r.gold_fact
        c.loop_pos += r.gold_loop
        c.loop_pred += p.create and not accepted_loop
        c.loop_hits += p.create and r.gold_loop
        if p.create and r.turn_created != "none":
            c.duplicates += 1
        elif p.create and not r.gold_loop and not r.also_loop:
            c.false_creates += 1
        c.false_resolve += p.resolve and not r.gold_resolves
        c.false_declared += p.declared and not r.gold_explicit
        if r.gold_loop:
            c.explicit_total += 1
            c.explicit_ok += p.declared == r.gold_explicit
        c.resolves_ok += p.resolve == r.gold_resolves
        if r.gold_choice == "waiting_on":
            c.waiting_total += 1
            c.waiting_written += p.wrote
        if choices is not None and r.turn_created == "none" and not r.gold_resolves:
            c.choice_total += 1
            c.choice_ok += choices[r.id] == r.gold_choice or (
                r.also_loop and choices[r.id] == "loop"
            )
        if r.turn_created != "none":
            c.link_total += 1
            c.link_ok += p.link_kind == r.turn_created
    return c


def verdict(system: Counts, baseline: Counts) -> tuple[bool, list[str]]:
    failing: list[str] = []
    if system.duplicates:
        failing.append(f"duplicate bookings {system.duplicates} != 0")
    if system.false_creates:
        failing.append(f"false loop creates {system.false_creates} != 0")
    if system.fact_precision < baseline.fact_precision:
        failing.append(
            f"fact precision {system.fact_precision:.3f} < baseline {baseline.fact_precision:.3f}"
        )
    if system.fact_recall < baseline.fact_recall - RECALL_SLACK:
        failing.append(
            f"fact recall {system.fact_recall:.3f} < baseline {baseline.fact_recall:.3f} - {RECALL_SLACK}"
        )
    if system.loop_precision < baseline.loop_precision:
        failing.append(
            f"loop precision {system.loop_precision:.3f} < baseline {baseline.loop_precision:.3f}"
        )
    if system.loop_recall < baseline.loop_recall - RECALL_SLACK:
        failing.append(
            f"loop recall {system.loop_recall:.3f} < baseline {baseline.loop_recall:.3f} - {RECALL_SLACK}"
        )
    if system.waiting_written:
        failing.append(
            f"waiting_on rows written to a store {system.waiting_written} != 0"
        )
    if system.false_resolve > baseline.false_resolve:
        failing.append(
            f"false resolves {system.false_resolve} > baseline {baseline.false_resolve}"
        )
    if system.choice_acc < MIN_CHOICE_ACCURACY:
        failing.append(
            f"Choice accuracy {system.choice_acc:.3f} < {MIN_CHOICE_ACCURACY}"
        )
    return not failing, failing


# --- live runs -----------------------------------------------------------------------


@dataclass
class RowResults:
    system: SystemOneResult
    r163: SystemOneResult
    r168: SystemOneResult


def shuffled_questions(rng: random.Random) -> dict[str, SystemOneQuestion]:
    """Option order shuffled per row (eval only) so position never carries signal."""
    questions = dict(COMMITMENT_QUESTIONS)
    for qid in SHUFFLED:
        base = COMMITMENT_QUESTIONS[qid]
        criteria = dict(base.criteria or {})
        keys = list(criteria)
        rng.shuffle(keys)
        questions[qid] = replace(base, criteria={k: criteria[k] for k in keys})
    return questions


async def run_rows(
    client: Any, rows: list[Row], seed: int, concurrency: int
) -> dict[str, RowResults]:
    async def one(index: int, row: Row) -> RowResults:
        rng = random.Random(seed * 100003 + index)

        async def ask(state: dict, questions: dict) -> SystemOneResult:
            return await client.evaluate(state, questions, max_attempts=1)

        return RowResults(
            await ask(build_state(row.text, row.assistant), shuffled_questions(rng)),
            await ask(state_163(row.text, row.assistant), shuffled_163(rng)),
            await ask(state_168(row.text), questions_168()),
        )

    done = await harness.bounded(rows, one, concurrency)
    return {r.id: rr for r, rr in zip(rows, done)}


# --- decisions at a given set of bars ------------------------------------------------


def make_cfg(*bars: float) -> CommitmentIntakeSurfaceConfig:
    return harness.surface_config(
        CommitmentIntakeSurfaceConfig, **dict(zip(BAR_NAMES, bars))
    )


def outcomes_for(
    rows: list[Row],
    results: dict[str, RowResults],
    cfg: CommitmentIntakeSurfaceConfig,
) -> dict[str, IntakeOutcome]:
    return {
        r.id: decide(results[r.id].system, cfg, r.created, tracked=False) for r in rows
    }


def preds_for(
    rows: list[Row],
    results: dict[str, RowResults],
    cfg: CommitmentIntakeSurfaceConfig,
) -> dict[str, Pred]:
    return {
        rid: pred_from_outcome(o) for rid, o in outcomes_for(rows, results, cfg).items()
    }


def baseline_preds(rows: list[Row], results: dict[str, RowResults]) -> dict[str, Pred]:
    out: dict[str, Pred] = {}
    for r in rows:
        b = decide_baseline(results[r.id].r163, results[r.id].r168)
        out[r.id] = pred_from_baseline(b.fact, b.loop)
    return out


def choices_for(
    rows: list[Row], results: dict[str, RowResults]
) -> dict[str, str | None]:
    return {r.id: predicted_choice(results[r.id].system) for r in rows}


# --- bar selection -------------------------------------------------------------------


def _centre(points: list[tuple[float, ...]]) -> tuple[float, ...]:
    """The plateau point closest to the plateau's median (a real grid point, not an average)."""
    dims = range(len(points[0]))
    median = [statistics.median(p[d] for p in points) for d in dims]
    return min(points, key=lambda p: sum((p[d] - median[d]) ** 2 for d in dims))


def _best_biography(
    rows: list[Row], results: dict[str, RowResults], choice: float
) -> float | None:
    """For one choice_hold: biography_hold at fact precision 1.0 and max fact recall."""
    best_key: tuple | None = None
    plateau: list[tuple[float, ...]] = []
    for bio in GRID:
        cfg = make_cfg(choice, choice, bio, 0.75, 0.85, 0.8)
        c = score(rows, preds_for(rows, results, cfg))
        if c.fact_hits == 0:
            continue
        key = (c.fact_precision != 1.0, -c.fact_recall)
        if best_key is None or key < best_key:
            best_key, plateau = key, [(bio,)]
        elif key == best_key:
            plateau.append((bio,))
    return _centre(plateau)[0] if plateau else None


def suggest_bars(
    rows: list[Row], results: dict[str, RowResults]
) -> CommitmentIntakeSurfaceConfig | None:
    """Per choice_hold (family_hold tied to it): the best biography bar for the fact side, then
    the (loop, resolves) plateau with zero duplicates and false creates and zero false resolves.
    The choice_hold with the fewest bad writes and the most fact plus loop recall wins; explicit
    is chosen last by fewest false declared. Centre of each plateau. Tuned set only."""
    best: tuple | None = None
    best_cfg: tuple[float, float, float, float] | None = None
    for choice in GRID:
        bio = _best_biography(rows, results, choice)
        if bio is None:
            continue
        loop_key: tuple | None = None
        plateau: list[tuple[float, ...]] = []
        for loop_hold in GRID:
            for resolves in GRID:
                cfg = make_cfg(choice, choice, bio, loop_hold, 0.85, resolves)
                c = score(rows, preds_for(rows, results, cfg))
                key = (
                    c.false_creates + c.duplicates,
                    c.fact_pred - c.fact_hits,
                    c.false_resolve,
                    -(c.loop_recall + c.fact_recall),
                )
                if loop_key is None or key < loop_key:
                    loop_key, plateau = key, [(loop_hold, resolves)]
                elif key == loop_key:
                    plateau.append((loop_hold, resolves))
        if loop_key is None or loop_key[0] != 0 or loop_key[1] != 0:
            continue
        if best is None or loop_key < best:
            best = loop_key
            loop_hold, resolves = _centre(plateau)
            best_cfg = (choice, bio, loop_hold, resolves)
    if best_cfg is None:
        return None
    choice, bio, loop_hold, resolves = best_cfg

    exp_key: tuple | None = None
    exp_plateau: list[tuple[float, ...]] = []
    for explicit in GRID:
        cfg = make_cfg(choice, choice, bio, loop_hold, explicit, resolves)
        c = score(rows, preds_for(rows, results, cfg))
        key = (c.false_declared, -c.explicit_acc)
        if exp_key is None or key < exp_key:
            exp_key, exp_plateau = key, [(explicit,)]
        elif key == exp_key:
            exp_plateau.append((explicit,))
    (explicit,) = _centre(exp_plateau)
    return make_cfg(choice, choice, bio, loop_hold, explicit, resolves)


# --- reports -------------------------------------------------------------------------


def _fmt(c: Counts) -> str:
    return (
        f"n={c.n} fb={c.fallback} "
        f"factP={c.fact_precision:.3f} factR={c.fact_recall:.3f} ({c.fact_hits}/{c.fact_pos}) "
        f"loopP={c.loop_precision:.3f} loopR={c.loop_recall:.3f} ({c.loop_hits}/{c.loop_pos}) "
        f"dup={c.duplicates} falseC={c.false_creates} falseRes={c.false_resolve} "
        f"falseDecl={c.false_declared} explAcc={c.explicit_acc:.3f} resAcc={c.resolves_acc:.3f}"
    )


def report_choice(rows: list[Row], results: dict[str, RowResults]) -> None:
    for lang in LANGS:
        in_lang = [r for r in rows if r.lang == lang]
        scoped = [
            r for r in in_lang if r.turn_created == "none" and not r.gold_resolves
        ]
        chosen = choices_for(scoped, results)
        ok = sum(chosen[r.id] == r.gold_choice for r in scoped)
        print(
            f"\n== [{lang}] Choice accuracy (turn created nothing, not a resolves row): {ok}/{len(scoped)} = "
            f"{ok / len(scoped) if scoped else 0:.3f} (skipped count as wrong)"
        )
        linked = [r for r in in_lang if r.turn_created != "none"]
        link_chosen = choices_for(linked, results)
        print(
            f"   rows where the turn created a reminder or goal ({len(linked)}): the outcome is a link"
            f" whatever the Choice says; Choice read as reminder/goal/loop on "
            f"{sum(link_chosen[r.id] in ('reminder', 'goal', 'loop') for r in linked)}"
        )
        print(
            "label".ljust(12)
            + "gold".rjust(6)
            + "pred".rjust(6)
            + "P".rjust(8)
            + "R".rjust(8)
        )
        for label in CHOICES:
            gold = [r for r in scoped if r.gold_choice == label]
            pred = [r for r in scoped if chosen[r.id] == label]
            hits = sum(chosen[r.id] == label for r in gold)
            precision = hits / len(pred) if pred else 1.0
            recall = hits / len(gold) if gold else 0.0
            print(
                label.ljust(12)
                + f"{len(gold):6d}{len(pred):6d}{precision:8.2f}{recall:8.2f}"
            )
        matrix: dict[str, Counter] = defaultdict(Counter)
        for r in scoped:
            matrix[r.gold_choice][chosen[r.id] or "skip"] += 1
        confused = [
            (g, p, n) for g, row in matrix.items() for p, n in row.items() if g != p
        ]
        if confused:
            print(
                "confusions (gold->pred:n): "
                + ", ".join(
                    f"{g}->{p}:{n}" for g, p, n in sorted(confused, key=lambda t: -t[2])
                )
            )


def show_reliability(rows: list[Row], results: dict[str, RowResults]) -> None:
    ok = [
        (r, results[r.id].system) for r in rows if results[r.id].system.outcome == "ok"
    ]
    commitment: list[tuple[float, bool]] = []
    family: list[tuple[float, bool]] = []
    for r, res in ok:
        a = res.answers.get(Q_COMMITMENT)
        if a is not None and a.confidence is not None:
            commitment.append((a.confidence, str(a.choice).lower() == r.gold_choice))
        f = res.answers.get(Q_FAMILY)
        if r.gold_fact and f is not None and f.confidence is not None:
            family.append((f.confidence, str(f.choice).lower() == r.gold_family))
    def table(title: str, points: list[tuple[float, bool]], label: str) -> None:
        harness.print_reliability(
            f"{title} (n={len(points)})",
            harness.reliability_bins(points),
            "mean_value",
            label,
            mean_width=9,
            show_ece=True,
        )

    table("commitment Choice confidence vs accuracy", commitment, "accuracy")
    table("family Choice confidence vs accuracy (fact rows)", family, "accuracy")
    noul_gold = {
        Q_BIOGRAPHY: ("gold_fact_rate", lambda r: r.gold_fact, None),
        Q_CONCERN: ("gold_loop_rate", lambda r: r.gold_loop, None),
        Q_EXPLICIT: (
            "gold_explicit_rate",
            lambda r: r.gold_explicit,
            lambda r: r.gold_loop,
        ),
        Q_RESOLVES: ("gold_resolves_rate", lambda r: r.gold_resolves, None),
    }
    for qid, (label, truth, only) in noul_gold.items():
        points = []
        for r, res in ok:
            a = res.answers.get(qid)
            if a is None or a.noul is None or (only and not only(r)):
                continue
            points.append((a.noul, bool(truth(r))))
        table(f"Noul reliability: {qid}", points, label)


def report_grids(rows: list[Row], results: dict[str, RowResults]) -> None:
    def scored(*bars: float) -> Counts:
        return score(rows, preds_for(rows, results, make_cfg(*bars)))

    harness.print_grid(
        "fact precision/recall (choice_hold=family_hold rows, biography_hold cols; "
        "loop bars fixed 0.75/0.85/0.8)",
        "choice\\bio ".ljust(11),
        harness.bar_grid(
            {"choice": GRID, "bio": GRID},
            lambda b: scored(b["choice"], b["choice"], b["bio"], 0.75, 0.85, 0.8),
        ),
        "choice",
        "bio",
        lambda c: f"{c.fact_precision:>7.2f}/{c.fact_recall:<4.2f}",
        width=12,
    )
    harness.print_grid(
        "dup+falseCreate / loop recall (loop_hold rows, resolves_hold cols; "
        "choice/family/biography 0.7, explicit 0.85)",
        "loop\\res   ",
        harness.bar_grid(
            {"loop": GRID, "res": GRID},
            lambda b: scored(0.7, 0.7, 0.7, b["loop"], 0.85, b["res"]),
        ),
        "loop",
        "res",
        lambda c: f"{c.duplicates + c.false_creates:>5d}/{c.loop_recall:<4.2f}",
        width=10,
        label_width=8,
    )


def report_errors(
    rows: list[Row],
    results: dict[str, RowResults],
    outcomes: dict[str, IntakeOutcome],
) -> None:
    """Tuned set only: rows whose outcome disagrees with the gold, with the answers behind it."""
    print("\n== tuned-set errors at the bars used (id, kind, gold -> outcome, answers)")
    for r in rows:
        o = outcomes[r.id]
        accepted_loop = r.also_loop and o.kind in CREATES
        bad = not accepted_loop and (
            (o.kind in CREATES) != r.gold_loop
            or (o.kind == "persist_fact") != r.gold_fact
        )
        bad = bad or (
            (o.kind == "resolve_loop") != r.gold_resolves
            or (r.gold_choice == "waiting_on" and o.kind in WRITES)
        )
        if not bad:
            continue
        vals = []
        for qid, a in results[r.id].system.answers.items():
            if a.noul is not None:
                vals.append(f"{qid[:7]}={a.noul:.2f}")
            elif a.choice is not None:
                vals.append(f"{qid[:7]}={a.choice}@{(a.confidence or 0):.2f}")
        print(
            f"  {r.id} {r.kind}: gold {r.gold_choice}/created={r.turn_created}"
            f" -> {o.kind}:{o.reason}  {' '.join(vals)}"
        )


def report_scores(
    rows: list[Row],
    results: dict[str, RowResults],
    cfg: CommitmentIntakeSurfaceConfig,
) -> dict[str, tuple[Counts, Counts]]:
    system_preds = preds_for(rows, results, cfg)
    base_preds = baseline_preds(rows, results)
    chosen = choices_for(rows, results)
    out: dict[str, tuple[Counts, Counts]] = {}
    for lang in (*LANGS, "all"):
        scoped = [r for r in rows if lang == "all" or r.lang == lang]
        out[lang] = (score(scoped, system_preds, chosen), score(scoped, base_preds))
        s, b = out[lang]
        print(f"\n== [{lang}]")
        print(
            f"  intake:   {_fmt(s)} choiceAcc={s.choice_acc:.3f}"
            f" linkAcc={s.link_acc:.3f} ({s.link_ok}/{s.link_total})"
        )
        print(f"  baseline: {_fmt(b)}")
        print(
            f"  waiting_on rows written to a store (SC-005): {s.waiting_written}/{s.waiting_total}"
        )
    return out


def describe(cfg: CommitmentIntakeSurfaceConfig) -> str:
    return (
        f"choice_hold={cfg.choice_hold} family_hold={cfg.family_hold} "
        f"biography_hold={cfg.biography_hold} loop_hold={cfg.loop_hold} "
        f"explicit_hold={cfg.explicit_hold} resolves_hold={cfg.resolves_hold}"
    )


def report_tuned(
    rows: list[Row],
    results: dict[str, RowResults],
    forced: CommitmentIntakeSurfaceConfig | None,
) -> None:
    report_choice(rows, results)
    show_reliability(rows, results)
    report_grids(rows, results)
    suggestion = suggest_bars(rows, results)
    cfg = forced or suggestion
    if cfg is None:
        print(
            "\nNo bar set reaches zero duplicates and false loop creates with a fact hit on this set."
        )
        cfg = make_cfg(0.9, 0.9, 0.9, 0.9, 0.9, 0.9)
    print(f"\nbars used: {describe(cfg)}")
    report_scores(rows, results, cfg)
    report_errors(rows, results, outcomes_for(rows, results, cfg))
    if suggestion:
        print(
            "\nSuggested bars (tuned set only): "
            f"choice_hold: {suggestion.choice_hold}  family_hold: {suggestion.family_hold}"
            f"  biography_hold: {suggestion.biography_hold}  loop_hold: {suggestion.loop_hold}"
            f"  explicit_hold: {suggestion.explicit_hold}  resolves_hold: {suggestion.resolves_hold}"
        )


def report_verdict(
    rows: list[Row], results: dict[str, RowResults], cfg: CommitmentIntakeSurfaceConfig
) -> None:
    out = report_scores(rows, results, cfg)

    def detail(s: Counts, b: Counts) -> str:
        return (
            f"intake: factP={s.fact_precision:.3f} factR={s.fact_recall:.3f}"
            f" loopP={s.loop_precision:.3f} loopR={s.loop_recall:.3f} dup={s.duplicates}"
            f" falseC={s.false_creates} falseRes={s.false_resolve} waitingWrites={s.waiting_written}/{s.waiting_total} choiceAcc={s.choice_acc:.3f}"
            f" linkAcc={s.link_acc:.3f} fallback={s.fallback}"
            f" | baseline: factP={b.fact_precision:.3f} factR={b.fact_recall:.3f}"
            f" loopP={b.loop_precision:.3f} loopR={b.loop_recall:.3f} dup={b.duplicates} falseRes={b.false_resolve}"
        )

    harness.print_verdict(
        {lang: (*verdict(*out[lang]), detail(*out[lang])) for lang in LANGS},
        lead=[f"bars: {describe(cfg)}"],
    )


# --- main ----------------------------------------------------------------------------


async def main_async(args: argparse.Namespace) -> int:
    if args.check_sets:
        return check_sets()
    if args.set in SPENT_SETS and not args.load:
        print(
            f"The {args.set} set is spent (verdict 2026-10-16). It stays loadable "
            "for reference through --replay only; a new verdict needs a fresh "
            "blind held-out file first (FR-020).",
            file=sys.stderr,
        )
        return 2
    if args.set == "holdout3" and not args.bars:
        print(
            "--replay on holdout3 needs the frozen --bars CHOICE,FAMILY,BIOGRAPHY,LOOP,EXPLICIT,RESOLVES.",
            file=sys.stderr,
        )
        return 2
    problems = shape_problems(
        load_rows(TUNED) if TUNED.exists() else None,
        load_rows(HOLDOUT),
        load_rows(HOLDOUT2) if HOLDOUT2.exists() else None,
        load_rows(HOLDOUT3) if HOLDOUT3.exists() else None,
    )
    if problems:
        print("Dataset problems; run --check-sets.", file=sys.stderr)
        return 1
    path = {
        "tuned": TUNED,
        "holdout": HOLDOUT,
        "holdout2": HOLDOUT2,
        "holdout3": HOLDOUT3,
    }[args.set]
    rows = load_rows(path)
    if args.set in SPENT_SETS:
        print("REFERENCE: spent held-out set, replayed offline. Not a verdict.")

    if args.load:
        results = {
            rid: RowResults(**v) for rid, v in harness.load_results(args.load).items()
        }
        missing = [r.id for r in rows if r.id not in results]
        if missing:
            print(
                f"--replay file lacks {len(missing)} rows of the set.", file=sys.stderr
            )
            return 1
        print(f"replaying {args.load} ({len(rows)} rows, no network)")
    else:
        client = harness.make_client(args)
        if client is None:
            return 2
        print(f"model={client._model} set={args.set} rows={len(rows)} seed={args.seed}")
        results = await run_rows(client, rows, args.seed, args.concurrency)
        if args.save:
            harness.save_results(args.save, results)
            print(f"raw results saved to {args.save}")

    skipped = Counter(
        (name, getattr(rr, name).skip_reason)
        for rr in results.values()
        for name in ("system", "r163", "r168")
        if getattr(rr, name).outcome == "skip"
    )
    if skipped:
        print(f"skipped requests (count as misses, never as writes): {dict(skipped)}")
    if all(rr.system.outcome == "skip" for rr in results.values()):
        print("Every intake call was skipped; nothing to calibrate.", file=sys.stderr)
        return 1

    if args.set == "holdout3":
        report_verdict(rows, results, args.bars_cfg)
    else:
        report_tuned(rows, results, args.bars_cfg)
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    harness.common_args(
        p,
        sets=("tuned", "holdout", "holdout2", "holdout3"),
        bars="CHOICE,FAMILY,BIOGRAPHY,LOOP,EXPLICIT,RESOLVES (required to replay --set holdout3)",
        seed=173,
        load_flags=("--load", "--replay"),
    )
    return p


def main() -> None:
    args = parser().parse_args()
    args.bars_cfg = (
        harness.bars_config(CommitmentIntakeSurfaceConfig, args.bars, BAR_NAMES)
        if args.bars
        else None
    )
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
