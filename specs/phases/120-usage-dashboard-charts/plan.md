# Implementation Plan: Usage Dashboard Charts

**Branch**: `120-usage-dashboard-charts` | **Date**: 2026-08-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/phases/120-usage-dashboard-charts/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Replace `CostsOverview.tsx`'s hand-rolled `SpendChart` (a raw `<svg>` bar row with hardcoded colors, no axis/legend/tooltip) with spec 118's `BarChart`, and add `PieChart`/`BarChart` proportion views above the existing "By plugin"/"By agent" breakdown panels. Purely a frontend rework — no backend or data-fetching change; `useCostsQuery`'s response already carries every field needed.

## Technical Context

**Language/Version**: TypeScript, React 19 (`apps/ze-web`)

**Primary Dependencies**: `packages/ze-ui`'s `BarChart`/`PieChart` (spec 118, no new dependency)

**Storage**: N/A

**Testing**: Vitest + React Testing Library (`make test-web`)

**Target Platform**: Web (React SPA)

**Project Type**: Web application (existing monorepo) — frontend-only change

**Performance Goals**: No new perf targets — same data, new rendering

**Constraints**: `fillDays()`'s existing 30-day zero-fill behavior must be preserved (FR-003)

**Scale/Scope**: One widget file (`CostsOverview.tsx`), removes one now-dead component (`SpendChart`), touches `TokenSplit` not at all (out of scope per research.md R3)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First Development** — PASS. Plan derived from `specs/phases/120-usage-dashboard-charts/spec.md`; status updated with implementation.
- **II. Single-User Model** — PASS (N/A). No scoping change.
- **III. Layered Package Architecture** — PASS. Purely within `apps/ze-web`, consuming `packages/ze-ui` as spec 118 already established. No new package, no new cross-layer dependency.
- **IV. Typed, Explicit Python** — PASS (N/A). No Python touched.
- **V. Test Discipline** — PASS, planned. `apps/ze-web` gains/updates component tests for `CostsOverview` covering the new chart renders and the removed `SpendChart`.
- **VI. Explicit Persistence** — PASS (N/A). No schema change.
- **VII. One LLM Gateway, Local Embeddings** — PASS (N/A).

No violations. Complexity Tracking: None.

## Project Structure

### Documentation (this feature)

```text
specs/phases/120-usage-dashboard-charts/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (repository root)

```text
apps/ze-web/src/widgets/costs-overview/
├── ui/
│   ├── CostsOverview.tsx      # EDIT — replace SpendChart usage with BarChart; add PieChart/BarChart to breakdown panels
│   └── SpendChart.tsx?        # DELETE (was inline in CostsOverview.tsx) — hand-rolled bar-row removed
└── ui/*.test.tsx              # NEW/EDIT — cover the new chart renders, zero-spend and single-day edge cases
```

**Structure Decision**: Single-widget change, no new files beyond tests — `SpendChart`/`TokenSplit` are currently local functions inside `CostsOverview.tsx`, not separate files; `SpendChart` is deleted from that file, `TokenSplit` stays (research.md R3).

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
