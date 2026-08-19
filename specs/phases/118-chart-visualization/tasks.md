---

description: "Task list template for feature implementation"
---

# Tasks: Chart Visualization for UI and Agent Responses

**Input**: Design documents from `/specs/phases/118-chart-visualization/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included — constitution Principle V (Test Discipline) is non-negotiable for this repo; every implementation task that adds behavior has a paired test task.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Web app monorepo — Python backend package (`core/ze-components`), shared TS UI-contract package (`packages/ze-ui`), React app (`apps/ze-web`). Paths below match `plan.md`'s Project Structure exactly.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Bootstrap the pieces every chart — agent-emitted or hand-placed — will need.

- [X] T001 Bootstrap a minimal `apps/ze-web/components.json` (shadcn CLI config: `tailwind.css` → `src/app/styles/globals.css`, aliases → existing `shared/ui`/`shared/lib` paths, `cn` → `shared/lib/cn`) so `pnpm dlx shadcn add @bklit/<chart>` can run non-interactively (research.md R2)
- [X] T002 [P] Add `--chart-1` through `--chart-5` CSS variables to `apps/ze-web/src/app/styles/globals.css`, derived from the existing "Open Sky" palette tokens (research.md R3)
- [X] T003 [P] Create `apps/ze-web/src/shared/ui/charts/` directory with an empty `index.ts` barrel export, ready to receive installed chart components

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Install and re-theme the starter chart component set. Both User Story 1 (agent emission covers line/bar/area per its acceptance scenarios) and User Story 2 (direct placement, sharing the same components per contracts/chart-primitive.md §3) depend on all three existing before either story can be considered done.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Install the Bklit line chart via `pnpm dlx shadcn add @bklit/line-chart` into `apps/ze-web/src/shared/ui/charts/line-chart.tsx`; re-theme any hard-coded classNames to Ze's existing token names (matching how `shared/ui/primitives/button.tsx` was adapted) (depends on T001, T002)
- [X] T005 [P] Install the Bklit bar chart via `pnpm dlx shadcn add @bklit/bar-chart` into `apps/ze-web/src/shared/ui/charts/bar-chart.tsx`; re-theme to Ze tokens (depends on T001, T002)
- [X] T006 [P] Install the Bklit area chart via `pnpm dlx shadcn add @bklit/area-chart` into `apps/ze-web/src/shared/ui/charts/area-chart.tsx`; re-theme to Ze tokens (depends on T001, T002)
- [X] T007 Export `LineChart`, `BarChart`, `AreaChart` from `apps/ze-web/src/shared/ui/charts/index.ts` (depends on T004, T005, T006)

**Checkpoint**: Foundation ready — chart components exist and are themed; user story implementation can now begin.

---

## Phase 3: User Story 1 - Agent shows a chart in the chat (Priority: P1) 🎯 MVP

**Goal**: An agent can emit chart data as part of a conversational response and the user sees it rendered inline, styled consistently with the app, in both light and dark theme.

**Independent Test**: Have an agent emit a line chart and a bar chart for two sample datasets in a conversation; confirm both render correctly with no per-conversation custom rendering code.

### Implementation for User Story 1

- [X] T008 [P] [US1] Create `Chart` and `ChartPoint` dataclasses in `core/ze-components/ze_components/organisms/chart.py`, mirroring `organisms/table.py`'s `Table` pattern (`type: Literal["chart"]` frozen discriminator, `chart_type: Literal["line", "bar", "area"]`) — data-model.md
- [X] T009 [US1] Register `Chart` in `PRIMITIVE_TYPES` and `ChartPoint` in `PRIMITIVE_SUB_TYPES`, export both from `core/ze-components/ze_components/__init__.py` (depends on T008)
- [X] T010 [US1] Add the private `_ChartSchema` dataclass and `render_chart` tool registration to `core/ze-components/ze_components/tools.py` per `contracts/chart-primitive.md` §1, including the wrapper-layer validation rules from data-model.md (drop malformed points, truncate at 500-point cap with a logged warning, defend against a stale `chart_type`) (depends on T008)
- [X] T011 [P] [US1] Test: `Chart`/`ChartPoint` JSON-schema export shape (discriminator, `$defs`, `maxItems`) in `core/ze-components/tests/test_schema.py` (depends on T009)
- [X] T012 [P] [US1] Test: `render_chart` tool schema and validation behavior (enum values, malformed-point drop, 500-point truncation) in `core/ze-components/tests/test_tools.py` (depends on T010)
- [X] T013 [US1] Regenerate `packages/ze-ui/src/generated/types.gen.ts` and `packages/ze-ui/src/generated/schema.json` from `ze_components.schema.export_json_schema()` (depends on T009)
- [X] T014 [US1] Add a `case "chart":` arm to `PrimitiveNodeRenderer`'s switch in `packages/ze-ui/src/react/PrimitiveRenderer.tsx`, dispatching to a new `ChartRenderer` that switches on `node.chart_type` to render `LineChart`/`BarChart`/`AreaChart` from `apps/ze-web/src/shared/ui/charts` (depends on T013, T007)
- [X] T015 [P] [US1] Test: `PrimitiveRenderer` chart cases — line/bar/area render without throwing, an unrecognized `chart_type` falls back to `null` per the file's existing default behavior — in `packages/ze-ui/src/react/PrimitiveRenderer.test.tsx` (depends on T014)
- [X] T016 [US1] Manual validation: live conversation chart rendering in both light and dark theme, per `quickstart.md` §3 (depends on T015)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently.

---

## Phase 4: User Story 2 - Developer adds a chart to a dashboard page (Priority: P2)

**Goal**: A developer can place a starter-set chart directly on a dashboard/analytics page, styled identically to the agent-emitted version, without writing new low-level rendering code.

**Independent Test**: Add a chart to one existing dashboard page (`apps/ze-web/src/pages/costs/ui/CostsPage.tsx`) with a static dataset and confirm it renders correctly, independent of any agent or SDUI code path.

### Implementation for User Story 2

- [X] T017 [US2] Add an example chart to `apps/ze-web/src/pages/costs/ui/CostsPage.tsx`, importing directly from `apps/ze-web/src/shared/ui/charts` with a small static dataset (depends on T007)
- [X] T018 [US2] Manual validation: confirm the directly-placed chart matches the same chart type rendered via the agent path (same colors, same chrome), per `quickstart.md` §4 (depends on T016, T017)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently.

---

## Phase 5: User Story 3 - Chart type coverage is extensible (Priority: P3)

**Goal**: A new chart type can be added later following the established pattern, as a purely additive change that doesn't affect existing chart types.

**Independent Test**: Add one chart type beyond the starter set (pie) end-to-end and confirm all existing chart-type tests still pass unchanged.

### Implementation for User Story 3

- [X] T019 [US3] Widen the `chart_type` `Literal` in `core/ze-components/ze_components/organisms/chart.py` to add `"pie"` (depends on T008)
- [X] T020 [P] [US3] Install the Bklit pie chart via `pnpm dlx shadcn add @bklit/pie-chart` into `apps/ze-web/src/shared/ui/charts/pie-chart.tsx`, re-theme to Ze tokens, export from `index.ts` (depends on T001, T002, T007)
- [X] T021 [US3] Add a `"pie"` branch to `ChartRenderer`'s dispatch in `packages/ze-ui/src/react/PrimitiveRenderer.tsx` (depends on T019, T020, T014)
- [X] T022 [P] [US3] Extend the test suites from T011/T012/T015 with `"pie"` cases; re-run the full suite and confirm the pre-existing line/bar/area assertions pass unchanged (SC-004) (depends on T021)

**Checkpoint**: All user stories should now be independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories.

- [X] T023 [P] Verify the empty/malformed-data edge cases (empty `data: []`, unsupported `chart_type`) render a graceful empty state rather than a crash or broken layout, per `quickstart.md` §5 (FR-005, FR-006)
- [ ] T024 [P] Verify chart legibility at narrow (side-panel) width per FR-009 / SC-003, across all implemented chart types and both themes
- [X] T025 Update `spec.md`'s Status header to `Implemented` and add/update the `specs/README.md` index row for `118-chart-visualization` in the same commit as the implementation (constitution Principle I)
- [X] T026 Run `make lint`, `make test-components`, and `make test-web`; all must pass clean before this feature is considered done (constitution Principle V)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS both User Story 1 and User Story 2
- **User Story 1 (Phase 3)**: Depends on Foundational completion — no dependency on User Story 2
- **User Story 2 (Phase 4)**: Depends on Foundational completion; T018's visual-parity check also depends on US1's T016 having established the agent-emitted reference rendering, but T017 itself only needs Phase 2
- **User Story 3 (Phase 5)**: Depends on User Story 1's Python/TS primitive plumbing (T008, T014) existing to extend
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — no dependency on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) — independently testable via its own static dataset; its parity check (T018) is easiest done after US1 exists but doesn't block US2's core implementation
- **User Story 3 (P3)**: Extends US1's mechanism directly — start after Phase 3 is complete

### Within Each User Story

- Dataclasses/schema before tool registration before codegen before renderer
- Tests follow their corresponding implementation task, asserting the behavior it introduces
- Story complete before moving to the next priority (though US2 can proceed in parallel with US1 once Phase 2 is done, per Parallel Opportunities below)

### Parallel Opportunities

- T002 and T003 (Setup) can run in parallel with T001
- T005 and T006 (Foundational) can run in parallel with T004, once T001/T002 are done
- T011 and T012 (US1 tests) can run in parallel with each other once their respective implementation tasks land
- US2's T017 can start as soon as Phase 2 (T007) is done — it does not need to wait for US1's Phase 3, only its final parity check (T018) does
- T020 (US3) can run in parallel with T019

---

## Parallel Example: Foundational Phase

```bash
# After T001/T002 land, install all three starter chart types together:
Task: "Install Bklit bar chart into apps/ze-web/src/shared/ui/charts/bar-chart.tsx"
Task: "Install Bklit area chart into apps/ze-web/src/shared/ui/charts/area-chart.tsx"
```

## Parallel Example: User Story 1

```bash
# Once render_chart (T010) and the PRIMITIVE_TYPES registration (T009) exist:
Task: "Test chart schema export in core/ze-components/tests/test_schema.py"
Task: "Test render_chart tool validation in core/ze-components/tests/test_tools.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks both remaining stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run `quickstart.md` §1–3 independently
5. Demo: an agent emitting a line/bar/area chart in a live conversation

### Incremental Delivery

1. Complete Setup + Foundational → chart components installed and themed
2. Add User Story 1 → validate independently → this is the MVP (agent-emitted charts)
3. Add User Story 2 → validate independently → developers can now hand-place charts too
4. Add User Story 3 → validate independently → pie chart proves the mechanism is additive
5. Polish phase closes out edge cases, narrow-layout legibility, and spec status

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (chart install/theming is one thread of work)
2. Once Foundational is done:
   - Developer A: User Story 1 (Python primitive + tool + TS renderer wiring)
   - Developer B: User Story 2 (dashboard page integration) — can start immediately, parity check waits on A
3. User Story 3 starts once Developer A's US1 plumbing (T008, T014) lands

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- The starter-set chart install (Phase 2) is intentionally shared/foundational rather than duplicated per story, since both US1 and US2 render the exact same components by design (contracts/chart-primitive.md §3)
