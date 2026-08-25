# Feature Specification: Data Overview Charts

**Feature Branch**: `122-data-overview-charts`

**Created**: 2026-08-19

**Status**: Implemented

**Input**: User description: "Rework the Data page (/data) using the new chart suite. Context: the page today shows total storage, a hand-rolled inline SVG donut chart (`StorageDonutChart`) breaking storage down by category, and a `By domain` breakdown panel using plain progress bars per domain (record count, storage size). This is one of 4 screens (Memory, Graph, Data, Usage) being reworked with the chart-visualization capability from spec 118-chart-visualization."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reading storage composition on a real chart (Priority: P1)

A user opens the Data page to see what's taking up storage — mostly memory? contacts? goals? Today this is shown as a hand-rolled inline SVG donut with no hover/tooltip interaction and hardcoded colors independent of the app's theme. The user wants this replaced with the app's standard chart component, interactive and consistently styled.

**Why this priority**: This is the page's single most prominent visualization and the clearest one-for-one replacement — swapping the hand-rolled donut for the new chart component directly improves the primary chart with the least redesign risk.

**Independent Test**: Load the Data page with storage spread across at least 3 categories; confirm the category breakdown renders using the app's standard chart component, with each category's exact size/percentage inspectable (e.g. via hover), not just visually estimated from wedge size.

**Acceptance Scenarios**:

1. **Given** a user has data spread across multiple categories, **When** they view the Data page, **Then** the category breakdown renders as a chart using the app's standard chart styling, and each category's value is inspectable.
2. **Given** a user has data in only one category, **When** they view the chart, **Then** it still renders sensibly for a single-category case rather than looking broken.
3. **Given** a user has no data yet in any domain, **When** they view the Data page, **Then** the chart shows a clear "no data yet" state rather than an empty or misleading chart.

---

### User Story 2 - Comparing domains within a category as a chart (Priority: P2)

A user expands a category group in the "By domain" panel (e.g. "Memory") and sees each domain's storage share as a plain thin progress bar. The user wants an easier way to compare domains within a group at a glance — for example, a bar chart of relative size across the domains in that group — while keeping the existing per-domain numeric detail (record count, byte size).

**Why this priority**: This is a real improvement to the secondary breakdown panel, but less impactful than fixing the primary chart — progress bars are functional today, just visually inconsistent with the new chart language and slightly harder to compare at a glance than a proper chart.

**Independent Test**: Expand a category group containing at least 3 domains with different sizes; confirm a chart-based comparison of relative size is shown alongside the existing per-domain numeric detail.

**Acceptance Scenarios**:

1. **Given** a category group has multiple domains of different sizes, **When** the user expands that group, **Then** a chart shows their relative size, and existing per-domain numbers (bytes, record count) remain visible.
2. **Given** a domain in the group has zero size (no data yet), **When** shown in the chart, **Then** it's represented as zero/absent rather than causing a broken render.

---

### Edge Cases

- What happens when total storage is exactly zero (brand-new install, no data anywhere)? The category chart must show a clear empty state, not a chart that looks broken or misleadingly full.
- What happens with a very large number of categories or domains (more than fit comfortably in a chart)? Charts must remain legible — grouping smaller categories or truncating gracefully rather than becoming unreadable.
- How do these charts behave at narrow viewport widths? They must remain legible, consistent with the narrow-layout requirement established for charts generally.
- What happens if a domain reports a record count but zero byte size (e.g. lightweight rows)? The chart must still represent it sensibly rather than treating it as absent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Data page's storage-by-category visualization MUST be rendered using the app's standard chart component, replacing the current hand-rolled implementation.
- **FR-002**: Each category in the storage chart MUST be inspectable for its exact value (size and/or percentage), not just visually estimated.
- **FR-003**: The "By domain" breakdown MUST include a chart-based comparison of relative size across domains within each expanded group, in addition to existing per-domain numeric detail — the numeric detail is not removed.
- **FR-004**: All charts on the Data page MUST use the app's theme color tokens — no hardcoded, one-off colors.
- **FR-005**: Charts on the Data page MUST render a sensible state for edge cases: zero total storage, a single category, and a large number of categories/domains — never a broken or blank render.
- **FR-006**: Charts on the Data page MUST remain legible at narrow viewport widths, consistent with the narrow-layout requirement established for charts generally.
- **FR-007**: The existing "By domain" grouping, expand/collapse behavior, and per-domain detail (importable badge, record count, byte size) MUST continue to work exactly as before — this feature adds and upgrades charts, it does not remove existing functionality.

### Key Entities

- **Storage Category Breakdown**: The existing category-level storage segmentation (already computed for the current donut chart), now rendered through the app's standard chart component — no new data.
- **Domain Size Comparison**: The existing per-domain size/record data within a category group, now additionally rendered as a chart-based comparison alongside its current numeric list form — no new data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can identify the largest storage category and its exact share within 5 seconds of viewing the Data page, using the chart.
- **SC-002**: A user can identify the largest domain within an expanded category group within 5 seconds, using the chart comparison.
- **SC-003**: Zero hardcoded colors remain in the Data page's chart-rendering code — 100% of chart colors resolve through the app's theme tokens.
- **SC-004**: All charts on the Data page render a valid, non-broken state across tested edge cases (zero storage, single category, many domains), verified for 100% of cases exercised.

## Assumptions

- This feature builds directly on the chart primitives and styling delivered in spec 118-chart-visualization; it does not introduce new chart types beyond that starter set unless a specific need is identified during planning.
- The underlying data (per-domain size, record count, category grouping) already exists via the Data page's current data source (`GET` data-domains query) and does not require new backend aggregation — only new presentation.
- The existing category grouping logic (prefix-based) and the export/import quick action are unaffected by this feature.
