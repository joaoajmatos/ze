# Implementation Plan: Memory Feed Charts

**Branch**: `121-memory-feed-charts` | **Date**: 2026-08-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/phases/121-memory-feed-charts/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add a memory-growth-over-time chart and a facts-vs-episodes composition chart to `/brain/memory`, both built on spec 118's chart components. Requires one additive backend change (`MemoryActivityDay` gains `fact_count`/`episode_count`, computed from a query that already unions the two but currently discards the split) and one bug-fix-adjacent wiring change (the page's activity query must respect the existing time-travel `asOfDate`, which it currently ignores).

## Technical Context

**Language/Version**: Python 3.11 (`core/ze-memory`, `apps/ze-api`) / TypeScript, React 19 (`apps/ze-web`)

**Primary Dependencies**: `packages/ze-ui`'s `LineChart`/`BarChart`/`PieChart` (spec 118); existing `GET /api/v0/memory/activity` endpoint

**Storage**: N/A — no schema/migration change; `memory_facts`/`memory_episodes` already have `created_at`, already queried

**Testing**: pytest (`make test-memory`), Vitest + React Testing Library (`make test-web`)

**Target Platform**: Web (React SPA)

**Project Type**: Web application (existing monorepo)

**Performance Goals**: No new perf targets — same query shape (labeled union instead of collapsed union), same result cardinality (one row per day)

**Constraints**: `_ACTIVITY_MAX_DAYS` cap (`core/ze-memory/ze_memory/admin.py`) already bounds query range — unaffected by this change

**Scale/Scope**: One endpoint gains two fields; one existing page gains two charts; one existing query call-site gets its `end` param corrected

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First Development** — PASS. Plan derived from `specs/phases/121-memory-feed-charts/spec.md`; status updated with implementation.
- **II. Single-User Model** — PASS (N/A). No scoping change.
- **III. Layered Package Architecture** — PASS. Backend change stays inside `ze-memory` → `ze-api`; frontend change stays inside `apps/ze-web`, consuming `packages/ze-ui` as already established.
- **IV. Typed, Explicit Python** — PASS. `MemoryActivityDay` stays a Pydantic model per the existing API-schema convention; the query change is raw SQL, no ORM.
- **V. Test Discipline** — PASS, planned. `core/ze-memory` gains a test for the `fact_count`/`episode_count` split; `apps/ze-web` gains component tests for both new charts and the as-of wiring fix.
- **VI. Explicit Persistence** — PASS (N/A). No migration.
- **VII. One LLM Gateway, Local Embeddings** — PASS (N/A).

No violations. Complexity Tracking: None.

## Project Structure

### Documentation (this feature)

```text
specs/phases/121-memory-feed-charts/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (repository root)

```text
core/ze-memory/ze_memory/admin.py             # EDIT — get_memory_activity: labeled union, group by (day, source)
apps/ze-api/ze_api/api/schemas.py             # EDIT — MemoryActivityDay gains fact_count, episode_count
core/ze-memory/tests/                          # EDIT — assert the split sums to count

packages/ze-client/src/generated/             # REGEN — types.gen.ts picks up the two new fields

apps/ze-web/src/pages/brain-memory/ui/
├── BrainMemoryPage.tsx                        # EDIT — render growth + composition charts; fix useMemoryActivityQuery's end param
└── BrainMemoryPage.test.tsx                   # NEW/EDIT — chart-placement + as-of wiring tests
```

**Structure Decision**: No new package, no new widget package — both charts render directly in `BrainMemoryPage.tsx` alongside the existing `TimelineScrubber`/`MemoryFeed`, matching where the page already assembles its time-oriented context (research.md R5).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

None — Constitution Check above passes with no violations.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
