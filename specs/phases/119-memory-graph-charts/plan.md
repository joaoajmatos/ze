# Implementation Plan: Memory Graph Charts

**Branch**: `119-memory-graph-charts` | **Date**: 2026-08-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/phases/119-memory-graph-charts/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add two chart-based views to the existing `/brain/graph` page, both consuming spec 118's `Chart` components directly (no SDUI path involved — this is entirely hand-placed UI): a per-entity activity-over-time chart in `EntityDetailPanel`, and a graph composition (entity/relation type) breakdown near the toolbar. Requires one small, additive backend change — `FactDigestItem` gains `created_at` (already computed, just not returned) so the activity chart isn't episodes-only.

## Technical Context

**Language/Version**: Python 3.11 (`core/ze-memory`, `apps/ze-api`) / TypeScript, React 19 (`apps/ze-web`)

**Primary Dependencies**: `packages/ze-ui`'s `LineChart`/`BarChart`/`PieChart` (spec 118, no new dependency); existing `GET /api/v0/memory/graph/entity/{id}` and `GET /api/v0/memory/graph` endpoints

**Storage**: N/A — no schema change; the one backend change surfaces an already-stored column (`memory_facts.created_at`) that isn't currently returned

**Testing**: pytest (`make test-memory`), Vitest + React Testing Library (`make test-web`)

**Target Platform**: Web (React SPA)

**Project Type**: Web application (existing monorepo)

**Performance Goals**: No new perf targets — both charts are computed from data already fetched for the page (entity detail, loaded graph nodes/edges), no new network round-trip beyond the one existing `created_at` field addition

**Constraints**: Composition chart must recompute on every graph expansion without noticeable lag at the page's existing node-count scale (single-user, dozens to low hundreds of loaded nodes)

**Scale/Scope**: Two new chart placements on one existing page; one additive backend field

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First Development** — PASS. Plan derived from `specs/phases/119-memory-graph-charts/spec.md`; status updated alongside implementation per Principle I.
- **II. Single-User Model** — PASS. No scoping change; entity/graph data is already single-user.
- **III. Layered Package Architecture** — PASS. The `created_at` field flows through the existing `ze-memory` → `ze-api` path; no new cross-package dependency. Chart placement is entirely within `apps/ze-web`, consuming `packages/ze-ui` as already established by spec 118.
- **IV. Typed, Explicit Python** — PASS. `FactDigestItem` stays a Pydantic model in `ze_api/api/schemas.py` (per the existing convention for API schemas); no new dataclass needed beyond the one field.
- **V. Test Discipline** — PASS, planned. `core/ze-memory` gains a test asserting `get_entity_detail` returns `created_at` on facts; `apps/ze-web`/`packages/ze-ui` gain component tests for both new chart placements.
- **VI. Explicit Persistence** — PASS (N/A). No migration — `memory_facts.created_at` already exists; only the read path changes.
- **VII. One LLM Gateway, Local Embeddings** — PASS (N/A). No LLM calls involved.

No violations. Complexity Tracking: None.

## Project Structure

### Documentation (this feature)

```text
specs/phases/119-memory-graph-charts/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (repository root)

```text
core/ze-memory/ze_memory/admin.py            # EDIT — get_entity_detail: select + return f.created_at
apps/ze-api/ze_api/api/schemas.py            # EDIT — FactDigestItem gains created_at: datetime
core/ze-memory/tests/                         # EDIT — assert created_at present on fact digest rows

packages/ze-client/src/generated/            # REGEN — types.gen.ts picks up FactDigestItem.created_at

apps/ze-web/src/widgets/memory-graph/
├── lib/
│   ├── entityActivitySeries.ts               # NEW — EntityDetailResponse -> ChartPoint[]
│   └── graphComposition.ts                   # NEW — GraphEntityNode[]/GraphEdge[] -> ChartPoint[]
├── ui/
│   ├── EntityDetailPanel.tsx                 # EDIT — render LineChart/BarChart of entity activity
│   ├── GraphToolbar.tsx                      # EDIT — render PieChart/BarChart composition breakdown
│   └── MemoryGraph.tsx                       # EDIT — pass current node/edge state down for composition calc
└── ui/*.test.tsx                             # NEW/EDIT — chart-placement tests
```

**Structure Decision**: No new packages. The backend field addition stays inside `ze-memory`'s existing service + `ze-api`'s existing schema (same pattern as any additive API field). Both new charts are pure frontend additions inside the existing `memory-graph` widget, consuming `packages/ze-ui`'s chart components exactly as `apps/ze-web/src/pages/costs/ui/CostsPage.tsx` already does per spec 118.

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
