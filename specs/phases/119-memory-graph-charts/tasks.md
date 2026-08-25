---

description: "Task list template for feature implementation"
---

# Tasks: Memory Graph Charts

**Input**: Design documents from `/specs/phases/119-memory-graph-charts/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included — constitution Principle V (Test Discipline) is non-negotiable for this repo.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

## Path Conventions

`core/ze-memory` (backend), `apps/ze-api` (schema), `packages/ze-client` (generated types), `apps/ze-web/src/widgets/memory-graph` (frontend) — per `plan.md`'s Project Structure.

---

## Phase 1: Setup

No new dependencies or scaffolding needed — this feature reuses spec 118's `packages/ze-ui` chart components and the existing `memory-graph` widget structure as-is.

---

## Phase 2: Foundational

**Note**: Unlike spec 118, this feature has no shared blocking prerequisite — User Story 1's backend change only serves User Story 1, and User Story 2 is entirely client-side. Each story's tasks appear directly in its own phase.

---

## Phase 3: User Story 1 - Understanding an entity's activity at a glance (Priority: P1) 🎯 MVP

**Goal**: The entity detail panel shows a chart of the selected entity's activity (facts + episodes) over time.

**Independent Test**: Select an entity with activity spread across multiple time periods; confirm a chart in the detail panel shows that activity distributed over time.

### Implementation for User Story 1

- [x] T001 [P] [US1] In `core/ze-memory/ze_memory/admin.py`'s `get_entity_detail` (~line 384), add `f.created_at` to the fact-rows `SELECT` and `"created_at": r["created_at"]` to the dict comprehension that builds each fact entry (contracts/entity-detail-created-at.md)
- [x] T002 [P] [US1] Add `created_at: datetime` to `FactDigestItem` in `apps/ze-api/ze_api/api/schemas.py:165`
- [x] T003 [P] [US1] Test: `get_entity_detail` returns `created_at` on fact rows, matching `memory_facts.created_at`, in `core/ze-memory/tests/`
- [x] T004 [US1] Regenerate `packages/ze-client/src/generated/types.gen.ts` via `bun run scripts/codegen.ts` (depends on T001, T002)
- [x] T005 [P] [US1] Create `entityActivitySeries(detail: EntityDetailResponse): ChartPoint[]` in `apps/ze-web/src/widgets/memory-graph/lib/entityActivitySeries.ts`, bucketing facts + episodes by day, tagging `series: "fact" | "episode"` (data-model.md)
- [x] T006 [US1] Render a `LineChart`/`BarChart` of the entity's activity in `apps/ze-web/src/widgets/memory-graph/ui/EntityDetailPanel.tsx`, above or alongside the existing Facts/Episodes lists, using `entityActivitySeries` (depends on T004, T005)
- [x] T007 [P] [US1] Test: `EntityDetailPanel` renders the activity chart for a multi-point entity, and renders a sensible state (not broken) for a single-point entity, in `apps/ze-web/src/widgets/memory-graph/ui/EntityDetailPanel.test.tsx` (depends on T006)
- [x] T008 [US1] Manual validation: `quickstart.md` §1–2 (depends on T007)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently.

---

## Phase 4: User Story 2 - Seeing the graph's composition, not just its shape (Priority: P2)

**Goal**: The graph page shows a chart breakdown of entity/relationship type composition for the currently loaded graph.

**Independent Test**: Open the graph page with a graph containing multiple entity types and relation types; confirm a composition chart is visible and its proportions match what's actually loaded.

### Implementation for User Story 2

- [x] T009 [P] [US2] Create `graphComposition(nodes: GraphEntityNode[], edges: GraphEdge[]): { byEntityType: ChartPoint[]; byRelationType: ChartPoint[] }` in `apps/ze-web/src/widgets/memory-graph/lib/graphComposition.ts` (data-model.md)
- [x] T010 [US2] In `apps/ze-web/src/widgets/memory-graph/ui/MemoryGraph.tsx`, compute the composition via `useMemo` keyed on the current node/edge arrays and pass it down (depends on T009)
- [x] T011 [US2] Render a `PieChart`/`BarChart` composition breakdown in `apps/ze-web/src/widgets/memory-graph/ui/GraphToolbar.tsx` (or a new small panel docked near it), fed by T010's computed data (depends on T010)
- [x] T012 [P] [US2] Test: composition chart reflects the loaded graph's entity-type proportions, updates when neighbours are expanded, and shows an empty state for zero loaded entities, in `apps/ze-web/src/widgets/memory-graph/ui/GraphToolbar.test.tsx` (depends on T011)
- [x] T013 [US2] Manual validation: `quickstart.md` §3 (depends on T012)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently.

---

## Phase 5: User Story 3 - A visually consistent, less dense graph page (Priority: P3)

**Goal**: The graph page's non-graph chrome matches the app's current design system.

**Independent Test**: Compare the graph page's toolbar, search bar, and detail panel styling against another already-redesigned page; confirm consistent colors, spacing, typography.

### Implementation for User Story 3

- [x] T014 [US3] Audit `EntityDetailPanel.tsx`, `GraphToolbar.tsx`, `GraphSearchBar.tsx` for any remaining hardcoded hex/rgba colors (`rtk proxy grep -n "#[0-9a-fA-F]\{3,6\}\|rgba(" apps/ze-web/src/widgets/memory-graph/ui/*.tsx`) and replace with existing theme tokens (research.md R5)
- [x] T015 [US3] Manual validation: `quickstart.md` §4 (depends on T014)

**Checkpoint**: All user stories should now be independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T016 [P] Verify edge cases per `quickstart.md` §5: single-date entity activity, empty-graph composition, narrow detail-panel legibility
- [x] T017 Update `spec.md`'s Status header to `Implemented` and the `specs/README.md` index row for `119-memory-graph-charts`, in the same commit as the implementation
- [x] T018 Run `make lint`, `make test-memory`, and `make test-web`; all must pass clean

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup / Foundational**: No blocking prerequisites — proceed directly to User Story 1.
- **User Story 1 (Phase 3)**: No dependency on other stories.
- **User Story 2 (Phase 4)**: No dependency on User Story 1 — entirely client-side, can run in parallel with Phase 3.
- **User Story 3 (Phase 5)**: Independent of US1/US2's specific chart content, but naturally done last since it's a final consistency pass over files US1/US2 also touch.
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### Parallel Opportunities

- T001/T002 (US1 backend) can run in parallel — different files.
- T005 (US1 chart-point mapping) can run in parallel with T001–T004 (backend work) — no dependency until T006 needs both.
- User Story 1 and User Story 2 can be implemented by different people entirely in parallel — neither depends on the other.

---

## Parallel Example: User Story 1

```bash
Task: "Add f.created_at to get_entity_detail's SELECT + dict in core/ze-memory/ze_memory/admin.py"
Task: "Add created_at: datetime to FactDigestItem in apps/ze-api/ze_api/api/schemas.py"
Task: "Create entityActivitySeries() in apps/ze-web/src/widgets/memory-graph/lib/entityActivitySeries.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 3 (User Story 1) — backend `created_at` field, activity chart in the detail panel.
2. **STOP and VALIDATE**: `quickstart.md` §1–2.
3. This alone answers "is this entity active or dormant?" — the spec's core value proposition.

### Incremental Delivery

1. User Story 1 → validate independently → ships the per-entity insight.
2. User Story 2 → validate independently → adds whole-graph orientation.
3. User Story 3 → validate independently → visual polish pass.

---

## Notes

- [P] tasks = different files, no dependencies.
- Commit after each task or logical group.
- User Stories 1 and 2 are genuinely independent — no artificial sequencing between them beyond convenience.
