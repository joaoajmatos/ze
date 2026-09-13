# Implementation Plan: User-Directed Priority Override

**Branch**: `127-priority-override` | **Date**: 2026-08-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/127-priority-override/spec.md`

## Summary

Give the user a snapshot view of `PriorityView`'s current ranked list (open
loops, stuck/near-gate goals, non-stale hypotheses) and two paths — drag in the
UI, or say so in chat — to reprioritize an item. Both paths express intent as a
user-stated `Contribution` (`source_function=EXECUTIVE`,
`provenance=PROMPT_SUPPLIED`, `target_face=ACTIVE_CONCERNS`) submitted through
`ze_collision.submit_and_detect_collisions()`, persisted as a new
`PriorityOverride` row (`ze-priority`, new `zpri` migration chain) that decays
toward `PriorityView`'s unmodified order over 48h unless pinned. A companion
`SYNTHESIZED`-provenance contribution representing `PriorityView`'s own current
computed position is submitted alongside it so Phase 126's collision detector
— whose same-`source_function` skip rule is narrowed to same-`(source_function,
provenance)` — can observe and log genuine user-vs-executive disagreement, per
research.md R1.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript (React 18, Vite) for
`ze-web`

**Primary Dependencies**: FastAPI, LangGraph (existing); new frontend
dependency `@dnd-kit/core` + `@dnd-kit/sortable` for the drag list (research.md
R9 — no existing drag-and-drop library in `ze-web`)

**Storage**: PostgreSQL via asyncpg — new table `priority_overrides` (research.md
R5, data-model.md), owned by `ze-priority`'s first migration chain (`zpri`)

**Testing**: pytest (`ze-priority/tests`, `ze-collision/tests` for the narrowed
skip rule, `ze-api/tests` for the new routes), vitest (`ze-web` widget/entity
hooks) — per Constitution V

**Target Platform**: Existing Ze backend (Linux/Docker) + React SPA — no new
deployment unit

**Project Type**: web (existing FastAPI + React monorepo)

**Performance Goals**: N/A beyond existing single-user, single-process
assumptions — the ranking merge (data-model.md) is an in-memory pure function
over at most a few dozen items; no new performance envelope

**Constraints**: Single-user model (Constitution II) — no per-user scoping on
`priority_overrides`. No live-update channel required (research.md R2/R6,
Clarifications Session 2026-08-26 Q3) — snapshot view recomputes on open/refresh
only.

**Scale/Scope**: Bounded by `PriorityView`'s existing three source lists (open
loops, stuck goals, non-stale hypotheses) — no new scale dimension.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Spec-First Development | Spec exists, clarified, status will be updated to `Planned` in this commit | Pass |
| II. Single-User Model | `priority_overrides` has no `user_id`/tenancy column; single API key auth reused | Pass |
| III. Layered Package Architecture | `PriorityOverride` storage + service logic lives in `ze-priority` (core, no domain knowledge beyond the three sources it already reads); `reprioritize_item` tool is a **core** tool (research.md R8), justified — not a plugin capability, since it needs direct `PriorityView` access and writes to the same `ACTIVE_CONCERNS` face `ze-worldstate` already writes from core. No new core-owned closed-enum member is added (research.md R1 explicitly rejects a new `SourceFunction`); `Provenance`/`SourceFunction` reused as-is. | Pass — see Complexity Tracking for the one cross-package modification (ze-collision) this still requires |
| IV. Typed, Explicit Python | `PriorityOverride` as a `types.py` dataclass; Pydantic only in `ze_api/api/schemas.py` for the new REST request/response models; `ZeError` subclass for override-not-found/stale-target errors | Pass |
| V. Test Discipline | Tests planned in `ze-priority/tests`, `ze-collision/tests`, `ze-api/tests`, `ze-web` vitest | Pass (enforced at `/speckit-tasks`/`/speckit-implement`) |
| VI. Explicit Persistence | New `zpri001` hand-written raw-SQL Alembic migration, no ORM | Pass |
| VII. One LLM Gateway, Local Embeddings | Disambiguation (tool-contract.md) reuses the existing local embedder singleton; no new LLM/embedding call site config | Pass |

No violations requiring justification beyond the one entry in Complexity
Tracking below (a modification to already-shipped Phase 126 code, not a new
architectural layer).

## Project Structure

### Documentation (this feature)

```text
specs/phases/127-priority-override/
├── plan.md              # this file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── rest-api.md
│   └── tool-contract.md
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
core/ze-priority/ze_priority/
├── types.py              # + PriorityOverride, PriorityOverrideRequest, SourceKind reuse
├── view.py                # unchanged (PriorityView.rank/rank_subset — read-only input)
├── scoring.py              # unchanged
├── store.py               # NEW — PriorityOverrideStore (Postgres)
├── merge.py                # NEW — ranking-merge pure function (data-model.md "Ranking merge")
├── contribution.py          # NEW — override_to_contribution() + synthesized-claim companion, mirrors ze_worldstate/contribution.py
├── service.py               # NEW — submit_reprioritization(), shared by REST route + tool
├── tools.py                # NEW — reprioritize_item @tool (Mode.CONFIRM)
├── errors.py                # + PriorityOverrideNotFoundError, StaleReprioritizationTargetError
└── migrations/
    └── zpri001_priority_overrides.py   # NEW chain, prefix `zpri`

core/ze-collision/ze_collision/
└── detect.py                # MODIFY _find_candidates(): skip rule → (source_function, provenance)

apps/ze-api/ze_api/
├── api/routes/priority.py    # NEW — GET /snapshot, POST /override, POST /override/{id}/unpin
├── api/schemas.py            # + PrioritySnapshotItem, PriorityOverrideRequest/Response models
├── container.py               # + priority_override_store wiring
└── migrate.py                 # + _ZE_PRIORITY_VERSIONS constant (research.md R5)

apps/ze-web/src/
├── entities/priority-item/
│   ├── api/usePrioritySnapshotQuery.ts
│   ├── api/useReprioritizeMutation.ts
│   └── index.ts
└── widgets/priority-snapshot/
    └── ui/PrioritySnapshot.tsx   # @dnd-kit sortable list + in-view disagreement indicator (FR-010)
```

**Structure Decision**: Existing monorepo layout (core/ package for domain
logic + apps/ze-api for the composition root + apps/ze-web for the SPA) — no
new package, no new deployment unit. `ze-priority` gains its first store and
migration chain; `ze-collision` gets one modified function in an
already-shipped module (see Complexity Tracking).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Modifying `ze_collision.detect._find_candidates()`'s skip rule (already-shipped Phase 126 code) | Without narrowing same-`source_function` to same-`(source_function, provenance)`, a user's `EXECUTIVE`/`PROMPT_SUPPLIED` override and `PriorityView`'s own `EXECUTIVE`/`SYNTHESIZED` computed claim can never be compared, so FR-010's "observable to Phase 126's collision detector" requirement is structurally impossible to satisfy (research.md R1) | Adding a new `SourceFunction` value was rejected (violates the doctrine-mandated closed seven-cognitive-function set); doing the comparison only client-side (skipping Phase 126 entirely) was rejected because the spec explicitly requires collision-log observability in addition to the in-view indicator |
