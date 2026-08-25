---

description: "Task list template for feature implementation"
---

# Tasks: Data Overview Charts

**Input**: Design documents from `/specs/phases/122-data-overview-charts/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included — constitution Principle V (Test Discipline) is non-negotiable for this repo.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

## Path Conventions

`apps/ze-web/src/widgets/data-overview` — single-widget frontend change, per `plan.md`'s Project Structure. No backend/API changes (contracts/no-backend-changes.md).

---

## Phase 1: Setup

No new dependencies or scaffolding — reuses spec 118's `packages/ze-ui` chart components.

## Phase 2: Foundational

No shared blocking prerequisite — User Story 1 (category chart) and User Story 2 (domain comparison chart) are independent additions to the same file.

---

## Phase 3: User Story 1 - Reading storage composition on a real chart (Priority: P1) 🎯 MVP

**Goal**: The "By category" breakdown renders using the app's standard chart component, replacing the hand-rolled SVG donut.

**Independent Test**: Load the Data page with storage spread across at least 3 categories; confirm the breakdown renders as a chart with each category's value inspectable.

### Implementation for User Story 1

- [x] T001 [US1] In `apps/ze-web/src/widgets/data-overview/ui/DataOverview.tsx`, replace the `<StorageDonutChart segments={segments} totalBytes={data.total_size_bytes} />` usage with `packages/ze-ui`'s `PieChart`, mapping `segments: CategorySegment[]` (unchanged, from existing `buildCategorySegments()`) to `ChartPoint[]` via `{x: label, y: bytes}`; delete `apps/ze-web/src/widgets/data-overview/ui/StorageDonutChart.tsx` (research.md R2, data-model.md)
- [x] T002 [P] [US1] Test: the category chart renders for multi-category data, a single-category account, and a zero-storage empty state, in `apps/ze-web/src/widgets/data-overview/ui/DataOverview.test.tsx` (new file, depends on T001)
- [x] T003 [US1] Manual validation: `quickstart.md` §1 (depends on T002)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently.

---

## Phase 4: User Story 2 - Comparing domains within a category as a chart (Priority: P2)

**Goal**: Each expanded "By domain" category group shows a chart-based comparison of relative domain size, alongside the existing per-domain numeric detail.

**Independent Test**: Expand a category group containing at least 3 domains with different sizes; confirm a chart-based comparison is shown alongside existing per-domain numbers.

### Implementation for User Story 2

- [x] T004 [US2] In `DataOverview.tsx`'s `BreakdownGroup` rendering, add a `BarChart` above each group's `DomainBreakdownItem` list, mapping that group's `domains: DataDomainItem[]` to `ChartPoint[]` via `{x: shortDomainName(domain.name), y: domain.size_bytes}` (data-model.md)
- [x] T005 [P] [US2] Test: the domain comparison chart renders for a group with 3+ domains of differing size, and represents a zero-size domain within the group as zero/absent rather than broken, in `DataOverview.test.tsx` (depends on T004)
- [x] T006 [US2] Manual validation: `quickstart.md` §2 (depends on T005)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T007 [P] Verify edge cases per `quickstart.md` §3: zero total storage, many categories/domains, narrow viewport
- [x] T008 [P] Verify no hardcoded colors remain per `quickstart.md` §4 (`rtk proxy grep -n "#[0-9a-fA-F]\{3,6\}\|rgba(" apps/ze-web/src/widgets/data-overview/**/*.tsx`)
- [x] T009 Update `spec.md`'s Status header to `Implemented` and the `specs/README.md` index row for `122-data-overview-charts`, in the same commit as the implementation
- [x] T010 Run `make lint` and `make test-web`; both must pass clean

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup / Foundational**: None — proceed directly to User Story 1.
- **User Story 1 (Phase 3)**: No dependency on other stories.
- **User Story 2 (Phase 4)**: No dependency on User Story 1 — different section of the same render tree (`BreakdownPanel`/`BreakdownGroup` vs the top-level category chart).
- **Polish (Phase 5)**: Depends on all desired user stories being complete.

### Parallel Opportunities

- User Story 1 and User Story 2 can be worked on in parallel — neither depends on the other's output, though both land in `DataOverview.tsx`.

---

## Parallel Example: User Story 1 & 2 (independent sections)

```bash
Task: "Replace StorageDonutChart usage with PieChart in DataOverview.tsx"
Task: "Add BarChart domain comparison inside BreakdownGroup in DataOverview.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 3 — replace `StorageDonutChart` with the real chart component.
2. **STOP and VALIDATE**: `quickstart.md` §1.
3. This alone fixes the page's most prominent visualization.

### Incremental Delivery

1. User Story 1 → validate independently → category chart fixed.
2. User Story 2 → validate independently → domain comparison added.

---

## Notes

- [P] tasks = different files or independent sections, no dependencies.
- Commit after each task or logical group.
- `lib/aggregate.ts`/`lib/format.ts` are reused unchanged throughout — no task touches them (research.md R2/R3).
