---

description: "Task list template for feature implementation"
---

# Tasks: Usage Dashboard Charts

**Input**: Design documents from `/specs/phases/120-usage-dashboard-charts/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included — constitution Principle V (Test Discipline) is non-negotiable for this repo.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

## Path Conventions

`apps/ze-web/src/widgets/costs-overview` — single-widget frontend change, per `plan.md`'s Project Structure. No backend/API changes (contracts/no-backend-changes.md).

---

## Phase 1: Setup

No new dependencies or scaffolding — reuses spec 118's `packages/ze-ui` chart components.

## Phase 2: Foundational

No shared blocking prerequisite — User Story 1 (spend chart) and User Story 2 (breakdown charts) touch different regions of the same file and can proceed independently.

---

## Phase 3: User Story 1 - Reading spend trends on a real chart (Priority: P1) 🎯 MVP

**Goal**: The daily spend trend renders as a real chart (hoverable, axis-aware), not a hand-rolled SVG bar row.

**Independent Test**: Load the Usage page with 30 days of spend history; confirm the spend trend renders as a chart with per-day value inspection.

### Implementation for User Story 1

- [x] T001 [US1] In `apps/ze-web/src/widgets/costs-overview/ui/CostsOverview.tsx`, remove the local `SpendChart` function (lines ~98–147) and replace its usage with `packages/ze-ui`'s `BarChart`, mapping `fillDays(by_day)` (kept as-is) to `ChartPoint[]` via `{x: date, y: usd}` (research.md R2, data-model.md)
- [x] T002 [P] [US1] Test: the spend chart renders 30 zero-filled points including a day with `usd: 0` shown as zero, in `apps/ze-web/src/widgets/costs-overview/ui/CostsOverview.test.tsx` (new file, depends on T001)
- [x] T003 [US1] Manual validation: `quickstart.md` §1 (depends on T002)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently.

---

## Phase 4: User Story 2 - Seeing cost breakdowns as charts, not just bars (Priority: P2)

**Goal**: The "By plugin" and "By agent" breakdown panels each show a chart-based proportion view alongside their existing numeric detail.

**Independent Test**: Load the Usage page with spend spread across at least 3 plugins; confirm the plugin breakdown shows a chart of relative spend, not only progress bars.

### Implementation for User Story 2

- [x] T004 [P] [US2] In `CostsOverview.tsx`, add a `PieChart` with `donut` above the "By plugin" `BreakdownPanel`, mapping `sortedPlugins` to `ChartPoint[]` via `{x: formatPluginName(plugin), y: usage.usd}` (data-model.md, research.md R3 — ring style)
- [x] T005 [P] [US2] Add the equivalent ring chart above the "By agent" `BreakdownPanel`, mapping `sortedAgents` (depends on nothing — parallel to T004, different section of the same return block)
- [x] T006 [P] [US2] Test: both breakdown charts render for multi-item data and a single-item case, and the existing `UsageItem` numeric list (percentage, calls, tokens, cost/call) remains present, in `CostsOverview.test.tsx` (depends on T004, T005)
- [x] T007 [US2] Manual validation: `quickstart.md` §2 (depends on T006)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently.

---

## Phase 5: User Story 3 - One consistent visual language across the whole page (Priority: P3)

**Goal**: No hardcoded colors remain on the Usage page; visualizations read as one coherent system.

**Independent Test**: Review every visualization on the Usage page; confirm none use colors outside the app's theme tokens.

### Implementation for User Story 3

- [x] T008 [US3] Confirm `SpendChart`'s removal (T001) eliminated the page's hardcoded hex/rgba fills: `rtk proxy grep -n "#[0-9a-fA-F]\{3,6\}\|rgba(" apps/ze-web/src/widgets/costs-overview/ui/*.tsx`; fix any remaining occurrence found (research.md R4 — expected to already be clean after T001, this is a verification task)
- [x] T009 [US3] Manual validation: `quickstart.md` §3 (depends on T008)

**Checkpoint**: All user stories should now be independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T010 [P] Verify edge cases per `quickstart.md` §4: 1-day-old account, zero total spend, 10+ plugins, narrow viewport
- [x] T011 Update `spec.md`'s Status header to `Implemented` and the `specs/README.md` index row for `120-usage-dashboard-charts`, in the same commit as the implementation
- [x] T012 Run `make lint` and `make test-web`; both must pass clean

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup / Foundational**: None — proceed directly to User Story 1.
- **User Story 1 (Phase 3)**: No dependency on other stories.
- **User Story 2 (Phase 4)**: No dependency on User Story 1 — touches a different section of `CostsOverview.tsx`'s render tree; can proceed in parallel if staffed separately, though both editing the same file means sequential commits are simpler in practice.
- **User Story 3 (Phase 5)**: Verification-only once T001 lands; trivially last.
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### Parallel Opportunities

- T004 and T005 (US2, plugin vs agent panel) touch different sections of the same file and can be done as one combined edit or split across two contributors' passes.
- User Story 1 and User Story 2 can be worked on in parallel by different people, merging into `CostsOverview.tsx` sequentially.

---

## Parallel Example: User Story 2

```bash
Task: "Add PieChart above 'By plugin' BreakdownPanel in CostsOverview.tsx"
Task: "Add PieChart above 'By agent' BreakdownPanel in CostsOverview.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 3 — replace `SpendChart` with the real chart component.
2. **STOP and VALIDATE**: `quickstart.md` §1.
3. This alone fixes the page's most-viewed, most visually broken element.

### Incremental Delivery

1. User Story 1 → validate independently → primary chart fixed.
2. User Story 2 → validate independently → breakdown panels upgraded.
3. User Story 3 → validate independently → confirms the whole page is now consistent.

---

## Notes

- [P] tasks = different files or independent sections, no dependencies.
- Commit after each task or logical group.
- This is a single-file rework (`CostsOverview.tsx`) — sequence commits carefully even where tasks are logically parallel.
