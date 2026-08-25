# Implementation Plan: Data Overview Charts

**Branch**: `122-data-overview-charts` | **Date**: 2026-08-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/phases/122-data-overview-charts/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Replace `DataOverview`'s hand-rolled `StorageDonutChart` (custom SVG stroke-dasharray donut with an independently-defined color palette) with spec 118's `PieChart`, and add a `BarChart` domain-size comparison inside each expanded "By domain" category group. Purely a frontend rework — no backend change; the existing `useDataDomainsQuery` response and `lib/aggregate.ts` helpers already carry everything needed.

## Technical Context

**Language/Version**: TypeScript, React 19 (`apps/ze-web`)

**Primary Dependencies**: `packages/ze-ui`'s `PieChart`/`BarChart` (spec 118, no new dependency)

**Storage**: N/A

**Testing**: Vitest + React Testing Library (`make test-web`)

**Target Platform**: Web (React SPA)

**Project Type**: Web application (existing monorepo) — frontend-only change

**Performance Goals**: No new perf targets — same data, new rendering

**Constraints**: `buildCategorySegments()`'s existing "other" bucketing (small-category folding) must be preserved as pre-processing before the pie chart, matching FR-005's many-categories edge case

**Scale/Scope**: One widget's two files (`DataOverview.tsx`, `StorageDonutChart.tsx` deleted); `lib/aggregate.ts`/`lib/format.ts` unchanged

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First Development** — PASS. Plan derived from `specs/phases/122-data-overview-charts/spec.md`; status updated with implementation.
- **II. Single-User Model** — PASS (N/A). No scoping change.
- **III. Layered Package Architecture** — PASS. Purely within `apps/ze-web`, consuming `packages/ze-ui` as already established.
- **IV. Typed, Explicit Python** — PASS (N/A). No Python touched.
- **V. Test Discipline** — PASS, planned. `apps/ze-web` gains/updates component tests for `DataOverview` covering the new chart renders and the removed `StorageDonutChart`.
- **VI. Explicit Persistence** — PASS (N/A). No schema change.
- **VII. One LLM Gateway, Local Embeddings** — PASS (N/A).

No violations. Complexity Tracking: None.

## Project Structure

### Documentation (this feature)

```text
specs/phases/122-data-overview-charts/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (repository root)

```text
apps/ze-web/src/widgets/data-overview/
├── ui/
│   ├── DataOverview.tsx           # EDIT — render PieChart for category breakdown; BarChart inside each BreakdownGroup
│   └── StorageDonutChart.tsx      # DELETE — replaced by packages/ze-ui's PieChart
├── lib/aggregate.ts               # unchanged — buildCategorySegments()/groupByPrefix() reused as-is
└── ui/*.test.tsx                  # NEW/EDIT — cover the new chart renders, zero-storage and single-category edge cases
```

**Structure Decision**: Single-widget change, no new files beyond tests — `lib/aggregate.ts` stays exactly as-is (research.md R2/R3), only the rendering layer changes.

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
