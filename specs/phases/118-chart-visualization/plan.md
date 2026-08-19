# Implementation Plan: Chart Visualization for UI and Agent Responses

**Branch**: `118-chart-visualization` | **Date**: 2026-08-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/phases/118-chart-visualization/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add a `chart` primitive (line/bar/area starter set) to `core/ze-components` and
`packages/ze-ui`, following the exact pattern every existing primitive (`Table`, `Steps`,
`Metric`) already uses — a `render_chart` `@tool` on the Python side, a discriminated-union
entry + `PrimitiveRenderer` case on the TS side — so agents can emit charts through the
existing render-tool mechanism and developers can place the same components directly on
dashboard pages. Chart rendering itself is sourced from Bklit UI (shadcn-registry chart
components, installed per-component via the shadcn CLI into `apps/ze-web`), re-themed to
Ze's existing "Open Sky" `@theme` tokens rather than left with default styling.

## Technical Context

**Language/Version**: Python 3.11 (backend, `core/ze-components`) / TypeScript, React 19 (frontend, `apps/ze-web`, `packages/ze-ui`)

**Primary Dependencies**: `ze-agents` (`@tool`), `ze_components.schema` (JSON-schema export), Bklit UI chart components (Recharts-based, installed as owned source via shadcn CLI) — no new runtime npm dependency beyond what the shadcn CLI pulls in per chart (`recharts`)

**Storage**: N/A — charts are stateless render primitives, not persisted entities

**Testing**: pytest (`make test-components`), Vitest + React Testing Library (`make test-web`)

**Target Platform**: Web (React SPA over WebSocket), no new platform surface

**Project Type**: Web application (existing monorepo: Python backend package + React frontend package)

**Performance Goals**: Charts render within the same turnaround as any other primitive in a message (no separate async load); no explicit new perf target beyond "doesn't visibly stutter" at the documented data-volume cap

**Constraints**: Agent-emittable chart data capped at 500 points per series (research.md R5); must theme correctly in both light and dark mode using existing `@theme` tokens (FR-004); new chart types must be addable without touching existing chart types' code (FR-008)

**Scale/Scope**: 3 starter chart types (line, bar, area); single-user scale data volumes (tens to low hundreds of points typical, per spec Assumptions)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First Development** — PASS. This plan is produced from `specs/phases/118-chart-visualization/spec.md`; status will be updated to `Planned` in this commit and to `Implemented` alongside the code per Principle I.
- **II. Single-User Model** — PASS. No user-scoping, no per-user chart config; charts are stateless render primitives.
- **III. Layered Package Architecture** — PASS. `Chart`/`ChartPoint` live in `core/ze-components` (no domain knowledge — chart data is just labeled numeric points, not tied to costs/goals/etc.); the TS renderer lives in `packages/ze-ui` (already the shared UI-contract package); Bklit components are installed into `apps/ze-web` (the composition root), not into `ze-ui` directly, matching where the existing shadcn-style primitives (`button.tsx`, etc.) already live. No new core-owned closed enum is introduced with domain vocabulary — `chart_type` is a rendering-shape enum (`line`/`bar`/`area`), not a plugin-domain value.
- **IV. Typed, Explicit Python** — PASS. `Chart`/`ChartPoint` are dataclasses in `types.py`-equivalent primitive modules (matching `Table`'s pattern in `organisms/table.py`), not Pydantic; no bare exceptions introduced.
- **V. Test Discipline** — PASS, planned. New tests land in `core/ze-components/tests/` (mocked, no real DB/LLM — schema/tool assertions only) and `packages/ze-ui/src/react/PrimitiveRenderer.test.tsx` (component render assertions), per research.md R6.
- **VI. Explicit Persistence** — PASS (N/A). No new tables; `Chart` is not persisted.
- **VII. One LLM Gateway, Local Embeddings** — PASS (N/A). No LLM calls added by this feature; `render_chart` is a tool the existing agent loop calls, using whatever `LLMClient` the calling agent already has.

No violations. Complexity Tracking section left empty.

## Project Structure

### Documentation (this feature)

```text
specs/phases/118-chart-visualization/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
core/ze-components/ze_components/
├── organisms/
│   └── chart.py              # NEW — Chart, ChartPoint dataclasses (mirrors organisms/table.py)
├── tools.py                  # EDIT — add _ChartSchema + render_chart tool registration
├── schema.py                 # unchanged — existing list[dataclass] handling covers Chart.data
└── __init__.py                # EDIT — export Chart/ChartPoint, add to PRIMITIVE_TYPES / PRIMITIVE_SUB_TYPES

core/ze-components/tests/
└── test_tools.py / test_schema.py   # EDIT — chart schema + render_chart assertions (research.md R6)

packages/ze-ui/src/
├── generated/                 # REGEN — types.gen.ts, schema.json (codegen from ze_components.schema)
└── react/
    ├── PrimitiveRenderer.tsx  # EDIT — add "chart" case + ChartRenderer dispatch on chart_type
    └── PrimitiveRenderer.test.tsx  # EDIT — line/bar/area render cases + unknown-type fallback

apps/ze-web/
├── components.json             # NEW — minimal shadcn CLI config scoped to this app (research.md R2)
├── src/app/styles/globals.css  # EDIT — add --chart-1…--chart-5 tokens (research.md R3)
└── src/shared/ui/charts/       # NEW — Bklit LineChart/BarChart/AreaChart, installed + re-themed
    └── (one file per chart type, e.g. line-chart.tsx, bar-chart.tsx, area-chart.tsx)
```

**Structure Decision**: Existing three-package split is reused as-is — no new package. Python
descriptor + tool logic goes in `core/ze-components` (already the SDUI-descriptor owner);
generated TS types + the renderer switch go in `packages/ze-ui` (already the shared
renderer); the actual Bklit chart component source is installed into `apps/ze-web` (the
composition root, matching where `shared/ui/primitives/*` already lives), then re-exported
for both the SDUI renderer's use and direct import by dashboard pages (contracts/chart-primitive.md §3).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

None — Constitution Check above passes with no violations.
