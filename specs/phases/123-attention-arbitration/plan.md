# Implementation Plan: Attention Arbitration — PriorityView + Shared Push Budget

**Branch**: `123-attention-arbitration` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/123-attention-arbitration/spec.md`

## Summary

Add a new core package, `ze-priority`, that exposes a read-only `PriorityView` query
combining currently-open `OpenLoop`s (ze-worldstate), stuck/near-gate goals
(ze-automation), and non-stale `Hypothesis`es (ze-correlation) into one ranked list on
the shared `Confidence` scale (`ze_agents.claims`, Phase 111). `ze-priority` also owns
a new `AttentionArbitrationJob` that replaces the two independently-scheduled push
sweeps (`ze_worldstate.jobs.push_sweep.PushSweepJob` and `ze_correlation`'s push
consumer trigger) with one sweep: gather push-eligible candidates from both
mechanisms (via new eligibility-only extraction methods that stop short of sending),
rank them through `PriorityView`, and atomically claim the shared daily push budget
for the single top-ranked candidate only. The shared budget primitive itself
(`within_budget`, claim/release) moves from `ze_correlation.push` into
`core/ze-proactive` per FR-006, fixing an existing cross-package dependency smell
(`ze_worldstate.surfacing` currently imports it from `ze_correlation`) along the way.
No new database tables; the existing `push_log` table gains one shared event key.

## Technical Context

**Language/Version**: Python 3.11 (matches repo-wide `pyproject.toml` pins)

**Primary Dependencies**: No new third-party dependencies. New internal package
depends on `ze-agents`, `ze-proactive`, `ze-worldstate`, `ze-automation`,
`ze-correlation` (all already in the monorepo).

**Storage**: PostgreSQL via `asyncpg`, reusing existing tables (`open_loops`, goal
tables, hypothesis tables, `push_log`). No new migration.

**Testing**: pytest, `asyncio_mode = "auto"`; unit tests mock the three store
Protocols/classes and `PushLogStore` with `AsyncMock` — no real DB, no real LLM (none
is called: ranking is deterministic, not LLM-based).

**Target Platform**: Backend service package, wired into `apps/ze-api` at startup
alongside the other proactive jobs.

**Project Type**: Single project — new core package within the existing monorepo
(`core/ze-priority/`).

**Performance Goals**: SC-001 — full ranked query in <500ms for a typical working set
(tens of open loops/goals/hypotheses); no source mechanism's own computation is
re-executed (FR-003), so cost is dominated by three store reads plus an O(n log n)
sort.

**Constraints**: Read-only projection (FR-003, no persisted `PriorityView` entity);
must not recompute drift detection, gate-proximity, or hypothesis novelty; shared
budget claim must be atomic (FR-008), not check-then-act.

**Scale/Scope**: Single user, tens of concurrently open items per source — no
pagination or indexing concerns beyond what the existing store queries already
provide.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Spec-First Development | Spec exists at `specs/phases/123-attention-arbitration/spec.md`, status will be updated to `Planned` → `Done` alongside implementation. | PASS |
| II. Single-User Model | No `user_id`, no multi-tenancy; budget and ranking are process-global for the one user. | PASS |
| III. Layered Package Architecture | `ze-priority` is a new **core** package (no domain knowledge of its own — it combines signals other core packages already compute) depending on other core packages (`ze-worldstate`, `ze-automation`, `ze-correlation`, `ze-proactive`, `ze-agents`), matching the existing precedent of `ze-worldstate → ze-correlation`. It is wired directly in `apps/ze-api` (composition root), not through `ze_sdk` (it is not a plugin extension point). | PASS |
| IV. Typed, Explicit Python | `PriorityItem`, `PriorityRanking` etc. as dataclasses in `types.py`; errors as `ZeError` subclasses; async store reads; constructor-injected stores/budget primitive. | PASS |
| V. Test Discipline | Unit tests in `core/ze-priority/tests/` mock all three store Protocols and `PushLogStore`. | PASS |
| VI. Explicit Persistence | No new tables. `push_log`'s existing schema (event_type, idempotency_key, unique index) is reused as-is with a new event-type value. | PASS |
| VII. One LLM Gateway | No LLM call in this feature — ranking is a deterministic function over existing `Confidence` values. | PASS |

No violations. Complexity Tracking section is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/phases/123-attention-arbitration/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
│   └── priority_view.md
└── tasks.md              # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
core/ze-priority/                          # NEW package
├── pyproject.toml
└── ze_priority/
    ├── types.py            # PriorityItem, PriorityRanking, SourceSignal dataclasses
    ├── scoring.py           # per-source Confidence adapters + deterministic tie-break
    ├── view.py              # PriorityView.rank() — the read-only query (FR-001..FR-004, FR-009)
    ├── arbitration.py        # AttentionArbitrationJob (FR-007, FR-008)
    └── tests/
        ├── test_view.py
        ├── test_scoring.py
        └── test_arbitration.py

core/ze-proactive/ze_proactive/
├── attention_budget.py       # NEW: within_budget() + try_claim_shared()/release_shared()
│                              #      (moved from ze_correlation.push, FR-005/FR-006)
└── tests/test_attention_budget.py   # NEW

core/ze-correlation/ze_correlation/
├── push.py                   # MODIFIED: within_budget/_PUSH_LOG_KEY removed; import from
│                              #   ze_proactive.attention_budget; consumer's autonomous
│                              #   scheduled trigger removed (superseded by AttentionArbitrationJob)
│                              #   push-building logic extracted into a reusable, send-only
│                              #   method the new job can call after winning arbitration
└── tests/test_push.py        # MODIFIED accordingly

core/ze-worldstate/ze_worldstate/
├── surfacing.py               # MODIFIED: within_budget import source changed; LoopSurfacer
│                              #   gains an eligibility-only method (candidates without sending)
├── jobs/push_sweep.py          # REMOVED: PushSweepJob superseded by AttentionArbitrationJob
└── tests/                     # MODIFIED accordingly

apps/ze-api/
├── ze_api/container.py        # Wire ze-priority's PriorityView + AttentionArbitrationJob
├── ze_api/compose.py           # Register AttentionArbitrationJob in place of PushSweepJob
│                              #   and correlation's push trigger
└── config/config.yaml          # Replace correlation.push.max_pushes_per_day,
                                #   correlation.salience.budget.max_pushes_per_day, and
                                #   worldstate.push.budget.max_pushes_per_day with a single
                                #   proactive.budget.max_pushes_per_day (= min of prior values)
```

**Structure Decision**: New core package `core/ze-priority` (no plugin involvement —
this is engine-level cross-cutting infrastructure, matching how `ze-worldstate` and
`ze-correlation` were structured). It is the only package positioned to depend on all
three source stores plus the shared budget primitive without creating a dependency
cycle: `ze-priority → {ze-worldstate, ze-automation, ze-correlation, ze-proactive,
ze-agents}`. The one shared scheduled job (`AttentionArbitrationJob`) therefore also
lives in `ze-priority`, not inside `ze-worldstate` or `ze-correlation` — putting the
orchestrator in either of those would require it to depend on the other, which
neither currently does and which this feature is not licensed to introduce (FR-010
keeps stores separate).

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*
