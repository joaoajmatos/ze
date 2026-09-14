# Implementation Plan: Contribution Collision Detection

**Branch**: `126-contribution-collision-detection` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Observe every write through Phase 124's `Contribution` seam (`ze_plugin.contribution.validate_and_submit`)
and, without altering that function or the write path's existing behavior, detect when two
contributions from *different* `source_function`s land on the same world-state face in genuine
content conflict (NLI-flagged, not mere co-occurrence) within a bounded recency window. Log the
collision (never block/delay/resolve either write) to a new, small, append-only store, queryable
via a REST endpoint. The technical crux resolved by this plan: `Contribution` today carries no
content, no entity linkage, and no ID — those live on each producer's own domain object — so the
detector is wired as a thin, opt-in wrapper (`submit_and_detect_collisions`) around
`validate_and_submit`, not a change to `validate_and_submit` itself, and a small `content`/
`entity_ids` extension is added to `Contribution` so each of the six existing call sites can pass
what it already has in hand.

## Technical Context

**Language/Version**: Python 3.12 (matches rest of monorepo; asyncio-native)

**Primary Dependencies**: `ze-agents` (`NLIClient` protocol, `ClaimKind`/`Provenance`), `ze-plugin`
(`Contribution`, `SourceFunction`, `TargetFace`, `validate_and_submit`), `ze-logging`
(`get_logger`), `asyncpg` (store), FastAPI (REST route, wired in `ze-api`)

**Storage**: PostgreSQL — one new append-only table (`contribution_collisions`), own migration
chain (prefix `zcol`), modeled on `ze-proactive`'s `PushLogStore`/`push_log` pattern

**Testing**: pytest, `asyncio_mode = "auto"`; mock `NLIClient.scores`/`AsyncMock` for asyncpg pool;
no real DB or LLM in unit tests, per constitution Principle V

**Target Platform**: Backend service (`apps/ze-api`), Linux/container deployment — no new
platform surface

**Project Type**: Backend addition to an existing monorepo (new core package + six call-site
edits + one REST route) — not a new app

**Performance Goals**: Collision check must not add observable latency to the write path it
observes (SC-003) — it runs *after* `write()` succeeds, wrapped in a hard timeout, and never
blocks the caller's return value

**Constraints**: Fail-open on any NLI error/timeout (FR-008); zero behavior change to
`validate_and_submit`'s existing validation/persistence/rejection contract (FR-001); no
interference with intra-function contradiction handling, e.g. `ze-memory`'s NLI fact-contradiction
path (FR-007)

**Scale/Scope**: Single-user system (constitution Principle II) — recency-window candidate scan is
over, at most, a handful of contributions per window per entity/target_face; no pagination
concerns beyond FR-009's filters

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec (126), governed by `ze-doctrine.md` §Arbitration and `contribution-seam.md` step 5's trigger condition, exists and is clarified before this plan | PASS |
| II. Single-User | No `user_id`/tenancy anywhere in `CollisionLogEntry` or the new store; single API key on the REST route like every other `/api/v0/` route | PASS |
| III. Layered Package Architecture | New package `core/seam/ze-collision` — no domain knowledge beyond the doctrine-mandated `SourceFunction`/`TargetFace`/`ClaimKind` closed enums it already consumes from `ze-plugin`/`ze-agents`; wired directly into `apps/ze-api` (same pattern as `ze-worldstate`, `ze-skills`) rather than folded into `ze-core`, because it owns its own tables/store/REST surface, which `ze-core`'s "no owned tables beyond engine internals" role doesn't fit. `SourceFunction`/`TargetFace` stay core-owned per the existing carve-out (doctrine-mandated closed sets) — this feature adds no new enum values, only reads them | PASS |
| IV. Typed, Explicit Python | `CollisionLogEntry` as a `types.py` dataclass; `ContributionError`-style typed error only if a genuine error path exists (there mostly isn't one — everything fails open); Pydantic confined to `ze_api/api/schemas.py` for the REST route | PASS |
| V. Test Discipline | Unit tests mock `NLIClient`/asyncpg per existing convention (`core/contracts/ze-plugin/tests/test_contribution.py`, `core/cognition/ze-worldstate/tests/test_contribution.py` as direct precedent) | PASS |
| VI. Explicit Persistence | Hand-written raw-SQL Alembic migration, new `zcol` chain owned by `ze-collision`, registered in `ze_api/migrate.py`'s `_ZE_COLLISION_VERSIONS` alongside the other non-plugin core packages | PASS |
| VII. One LLM Gateway / Local Embeddings | Reuses the existing injected `NLIClient` (local cross-encoder) — no new LLM call, no new embedding model | PASS |

No violations. Complexity Tracking section left empty.

## Project Structure

### Documentation (this feature)

```text
specs/phases/126-contribution-collision-detection/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── collisions-api.md
└── tasks.md              # Phase 2 output (/speckit-tasks — not this command)
```

### Source Code (repository root)

```text
core/seam/ze-collision/                       # NEW package
├── pyproject.toml
├── ze_collision/
│   ├── types.py            # CollisionLogEntry, CollisionCandidate
│   ├── store.py             # CollisionLogStore Protocol + PostgresCollisionLogStore
│   ├── detect.py            # submit_and_detect_collisions() wrapper, pairwise NLI check,
│   │                        # recency-window candidate scan, fail-open discipline
│   ├── rest.py               # list_collisions() query-surface function (entity/source_function/date filters)
│   └── migrations/
│       └── versions/
│           └── zcol001_contribution_collisions.py
└── tests/
    ├── test_detect.py
    ├── test_store.py
    └── test_rest.py

core/contracts/ze-plugin/ze_plugin/contribution.py   # MODIFIED — add optional content/entity_ids
                                            # fields to Contribution; validate_and_submit's
                                            # own behavior is unchanged (FR-001)

core/cognition/ze-worldstate/ze_worldstate/
├── contribution.py                        # MODIFIED — loop_to_contribution() populates
│                                           #  content= (loop.title) and entity_ids=
└── extraction.py                          # MODIFIED — call submit_and_detect_collisions()
                                            #  instead of validate_and_submit() (2 call sites)

core/cognition/ze-memory/ze_memory/
├── contribution.py                        # MODIFIED — signal_to_contribution() populates
│                                           #  content= (signal.title + summary), entity_ids=
├── retriever.py                           # MODIFIED — 1 call site
└── dream/dream_pass.py                    # MODIFIED — 1 call site, content= param already
                                            #  available (dream artifact `content`)

core/cognition/ze-correlation/ze_correlation/engine.py  # MODIFIED — 1 call site, content= from
                                               #  hypothesis, entity_ids from hypothesis evidence

plugins/ze-personal/ze_personal/
├── contacts/contribution.py               # MODIFIED — person_source_to_contribution()
├── contacts/consolidator.py               # MODIFIED — 2 call sites
└── graph/memory_hooks.py                  # MODIFIED — 2 call sites

apps/ze-api/ze_api/
├── container.py                           # MODIFIED — wire CollisionLogStore + NLIClient
│                                           #  into ze_collision.detect
├── migrate.py                             # MODIFIED — add _ZE_COLLISION_VERSIONS
└── api/routes/collisions.py               # NEW — GET /api/v0/collisions
```

**Structure Decision**: New core package `core/seam/ze-collision`, following the precedent of
`ze-worldstate`/`ze-skills`/`ze-correlation` (a bounded cross-cutting substrate with its own
store, migrations, and REST surface, wired directly by `ze-api` rather than folded into
`ze-core`). Twelve existing files across five packages get a small, mechanical edit each: extend
`Contribution` with two optional fields, and swap `validate_and_submit(...)` for
`submit_and_detect_collisions(...)` at each of the six production call sites found via
`grep -rn "validate_and_submit" core plugins`.

## Complexity Tracking

*No Constitution Check violations — section intentionally empty.*
