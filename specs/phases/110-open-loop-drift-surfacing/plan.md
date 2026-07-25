# Implementation Plan: Open-Loop Drift Detection & Surfacing

**Branch**: `110-open-loop-drift-surfacing` | **Date**: 2026-07-23 | **Spec**: [spec.md](./spec.md)

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Phase B of the open-loop substrate. Add two capabilities on top of Phase A's `ze-worldstate`
package: (1) **drift detection** — a scheduled sweep plus an immediate contradiction-triggered
path that moves `active` loops into the already-defined `drifting` state, backed by two new
columns on `open_loops` (`drift_deadline`, `drift_rationale`) and a minimal, optional extension
to the extraction gate so a loop can carry an implied timeframe; and (2) **surfacing** — a new
`ze_core` orchestration node (sequenced after, not inside, the existing `correlate` node) that
inline-mentions a topically-relevant `drifting` loop via entity-link overlap, and a new
`ze-worldstate` proactive job that pushes a high-bar-clearing `drifting` loop through a direct
new `ze-worldstate → ze-correlation` dependency that reuses (via extraction, not duplication)
the correlation engine's threshold/novelty/grounding/budget push-bar functions against a sibling
push-log key and its own configured daily budget. No lifecycle transition in this feature is
ever autonomous beyond `active → drifting`; `drifting → closed/dropped` remains user-only
(Phase A's `review.py`, unchanged).

## Technical Context

**Language/Version**: Python 3.11 (matches the rest of the monorepo)

**Primary Dependencies**: `ze-agents` (logging/errors/NLI client protocol), `ze-proactive`
(drift-sweep + push-sweep jobs, same pattern as Phase A's stale-suspicion job), `ze-memory`
(entity-anchor matching for topical relevance, `GraphStore`), `ze-correlation` (**new** direct
dependency — reused push-bar mechanics), `ze-core` (the new inline-surfacing orchestration node
lives here, injected via `config["configurable"]` exactly like `correlation_engine` is today, so
`ze_core` itself never imports `ze_worldstate`)

**Storage**: PostgreSQL via `asyncpg`; two new nullable columns on the existing `open_loops`
table (`drift_deadline TIMESTAMPTZ`, `drift_rationale TEXT`) added on the `zw` chain
(`zw002_drift_columns.py`); no new tables — surfacing decisions reuse `ze-proactive`'s existing
`push_log` table with a new, distinct `event_type` key so the budget is a sibling counter, not a
shared one

**Testing**: `pytest`, `asyncio_mode = "auto"`, `AsyncMock` for asyncpg pools, no real DB/LLM/embedder
in unit tests, per `docs/testing.md`; orchestration-node test mocks `config["configurable"]`
exactly as the existing `core/ze-core/tests/orchestration/nodes/test_correlation.py` does — the
new test lives in the same suite (`test_loop_surfacing.py`)

**Target Platform**: Linux server (existing `ze-api` deployment; FastAPI/uvicorn + LangGraph)

**Project Type**: Backend package extension — additions to the existing `core/ze-worldstate`
package, a new node in `core/ze-core/ze_core/orchestration/nodes/`, a small extraction of
reusable functions out of `core/ze-correlation/ze_correlation/push.py`, and `ze-api` wiring
(jobs, graph configurable injection, config.yaml). No new frontend surface — Phase A's loop
review list already renders `drifting` loops and gains a `drift_rationale` field for free once
the REST payload includes it (Assumptions: "No new UI paradigm").

**Performance Goals**: Drift sweep and push sweep run as low-frequency scheduled jobs (daily /
few-times-daily cadence, matching the stale-suspicion and correlation-push cadences); the inline
surfacing node runs synchronously inside the conversation turn and must stay cheap — entity-link
overlap only (a `GraphStore` lookup already paid for by matching.py's existing infra), no LLM
call, no new embedding call per turn (per Clarification).

**Constraints**: Single-user (no `user_id` scoping); reflection-only inference posture — no
autonomous `drifting → closed/dropped/active` transition anywhere in this feature (FR-010);
push must re-check current loop state immediately before sending (FR-011); a loop mentioned
inline suppresses a push of the same loop for a short cooldown (FR-012).

**Scale/Scope**: Same single-user scale as Phase A — drift/push sweeps iterate over a low
hundreds-of-loops working set; no new scale concern.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Spec-First Development | Spec at `specs/phases/110-open-loop-drift-surfacing/spec.md`, clarified (5 questions answered); status flips to `Planned`/`In Progress` in the implementing commit | PASS |
| II. Single-User Model | No `user_id` anywhere in the new columns, jobs, or push-log keys | PASS |
| III. Layered Package Architecture | Drift/push logic stays inside `ze-worldstate` (core, non-plugin, same reasoning as Phase A). The one new package-graph edge — `ze-worldstate → ze-correlation` — is explicit, ratified by Clarification, and is between two **core** packages (no plugin boundary crossed). The inline node is added to `ze-core`'s orchestration graph but reads its dependency (a `LoopSurfacer`-shaped object) only via `config["configurable"]`, exactly as `correlate`'s `correlation_engine` is — so `ze_core` gains **no** import-time dependency on `ze_worldstate`, preserving "engine has no domain knowledge." `CLAUDE.md`'s dependency graph table is updated in the same commit per the Clarification and the Governance principle. | PASS |
| IV. Typed, Explicit Python | New fields on the existing `OpenLoop` dataclass in `types.py` (never `models.py`); typed errors reused from Phase A (`errors.py`); async I/O throughout; constructor injection for the new jobs and the inline node's surfacer object | PASS |
| V. Test Discipline | New tests in `core/ze-worldstate/tests/jobs/test_drift_sweep.py`, `test_push_sweep.py`, `core/ze-worldstate/tests/test_decay.py` (extended for FR-002), `core/ze-correlation/tests/test_push.py` (extended after the bar-function extraction), and a new orchestration-node test in `core/ze-core/tests/`; no real DB/LLM/embedder | PASS (planned) |
| VI. Explicit Persistence | One new migration `zw002_drift_columns.py` continuing the existing `zw` chain owned by `ze-worldstate`; no ORM; no new table (push-log reuse is row-level, not schema-level) | PASS |
| VII. One LLM Gateway, Local Embeddings | Grounding check reuses the already-injected `NLIClient`; no new provider dependency; inline surfacing explicitly avoids a new embedding call per Clarification | PASS |

No violations requiring Complexity Tracking, with one deliberate, ratified exception recorded
below for transparency (not a violation — the Clarifications already authorize it).

## Project Structure

### Documentation (this feature)

```text
specs/phases/110-open-loop-drift-surfacing/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── surfacing.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
core/ze-worldstate/
├── pyproject.toml                        # add "ze-correlation" to dependencies
├── ze_worldstate/
│   ├── types.py                          # OpenLoop gains drift_deadline, drift_rationale
│   ├── decay.py                          # cascade_from_evidence: on ACTIVE + confidence drop
│   │                                     #   from contradiction, transition -> DRIFTING (FR-002)
│   ├── drift.py                          # NEW — drift-window computation, sweep-eligibility
│   │                                     #   query predicate, rationale composition (FR-001/005)
│   ├── surfacing.py                      # NEW — LoopSurfacer: inline eligibility (entity-overlap,
│   │                                     #   FR-006) + push eligibility (delegates bar checks to
│   │                                     #   ze_correlation.push, FR-007/008/011/012)
│   ├── store.py                          # LoopStore: + set_drift_deadline, set_drift_rationale,
│   │                                     #   list_drift_candidates(); link_evidence now touches
│   │                                     #   updated_at (drift "fresh evidence" signal)
│   ├── extraction.py                     # extraction gate JSON schema gains optional
│   │                                     #   "implied_window_days"; sets drift_deadline at
│   │                                     #   confirm-time (review.confirm_loop)
│   ├── review.py                         # confirm_loop sets drift_deadline = now + window
│   ├── rest.py                           # loop list/detail payload includes drift_rationale
│   ├── bootstrap.py                      # wires drift + push jobs, LoopSurfacer construction
│   ├── jobs/
│   │   ├── drift_sweep.py                # NEW — ze-proactive job, FR-001/003/004
│   │   └── push_sweep.py                 # NEW — ze-proactive job, FR-007/008/011
│   └── migrations/versions/
│       └── zw002_drift_columns.py        # NEW — drift_deadline, drift_rationale columns
└── tests/
    ├── test_drift.py
    ├── test_surfacing.py
    └── jobs/
        ├── test_drift_sweep.py
        └── test_push_sweep.py

core/ze-correlation/
└── ze_correlation/
    └── push.py                           # extract passes_confidence, passes_novelty,
                                          #   passes_grounding, within_budget as free functions
                                          #   parameterized on (summary, confidence, relevance,
                                          #   evidence_labels, event_key) so both
                                          #   CorrelationPushConsumer and ze-worldstate's
                                          #   LoopSurfacer call the same bar, not two bars

core/ze-core/
└── ze_core/orchestration/
    ├── nodes/
    │   └── loop_surfacing.py             # NEW — mirrors nodes/correlation.py's shape; reads
    │                                     #   config["configurable"]["loop_surfacer"]; adds its
    │                                     #   own "drifting loop" component + text section
    └── graph.py                          # add_node("surface_loops", ...) sequenced after
                                          #   "correlate": correlate -> surface_loops -> (route).
                                          #   after_correlate's edge target changes from
                                          #   {"synthesize","record_trace"} to a single
                                          #   unconditional edge into surface_loops; the routing
                                          #   decision (synthesize vs record_trace) moves to a new
                                          #   after_surface_loops function with identical logic

apps/ze-api/
├── config/config.yaml                    # worldstate.drift{window_days, cron}, worldstate.push
│                                         #   {enabled, cron, budget, thresholds}
├── ze_api/
│   ├── container.py                      # inject loop_surfacer into graph configurable,
│   │                                     #   same call shape as correlation_engine
│   ├── compose.py                        # register drift_sweep + push_sweep jobs
│   └── migrate.py                        # zw chain already discovered; no change beyond the
                                          #   new versions file being picked up automatically

CLAUDE.md                                 # package dependency graph table: ze-worldstate row
                                          #   gains "ze-correlation" dependency (same commit)
```

**Structure Decision**: All new domain logic stays inside `core/ze-worldstate`, following Phase
A's shape (a `jobs/` module per scheduled sweep, a `bootstrap.py` stack builder, `rest.py` plain
functions). The only structurally new things are (1) a genuinely new package dependency edge
`ze-worldstate → ze-correlation`, ratified by Clarification and reflected in `CLAUDE.md`, used
for exactly one purpose — reusing extracted push-bar functions — and (2) a new orchestration
node in `ze-core`, sequenced immediately after `correlate` in the same linear chain
(`correlate -> surface_loops -> route`), injected via `config["configurable"]` at invocation time
the same decoupled way `correlate`'s dependency already is — never imported at module scope, so
`ze-core`'s "no domain knowledge" invariant holds even though a loop-shaped concept now has a
graph node.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

No unratified violations. The one new package-dependency edge (`ze-worldstate →
ze-correlation`) is not treated as a violation because Clarification session 2026-07-23
explicitly evaluated and chose it over the alternative (reimplementing the push bar inside
`ze-worldstate`), reasoning that a second, divergent implementation of the same
confidence/relevance/novelty/grounding/budget algorithm is a larger long-term liability than one
more edge between two core (non-plugin, non-engine) packages. Table intentionally omitted.

## Extension Hooks

No `.specify/extensions.yml` file exists in this repository, so no pre- or post-plan hooks were
found or executed.
