# Feature Specification: Usage Dashboard Charts

**Feature Branch**: `120-usage-dashboard-charts`

**Created**: 2026-08-19

**Status**: Implemented

**Input**: User description: "Rework how the whole usage and data screen looks using a suite of new graphs and charts. Context: the Usage page (`/costs`, `CostsOverview` widget) currently renders spend history as a hand-rolled inline SVG bar chart (`SpendChart`, no axis/legend/tooltip, hardcoded hex colors instead of the app's theme tokens) and shows the prompt/completion token split as a two-segment progress bar (`TokenSplit`). Both predate the chart-visualization capability just shipped in spec 118-chart-visualization (core/ze-components Chart/ChartPoint primitive, packages/ze-ui chart renderer with line/bar/area/pie via Bklit). The user wants the whole usage/data screen reworked to use the new chart suite instead of these one-off hand-rolled visualizations."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reading spend trends on a real chart (Priority: P1)

A user opens the Usage page to understand how their spend has trended over the last 30 days. Today they see a row of plain colored bars with no axis labels, no legend, and no way to hover a specific day to see its exact value — just a hardcoded "30 days ago" / "today" caption underneath. The user wants a proper chart here: hoverable, with clear per-day values, styled consistently with charts elsewhere in the app.

**Why this priority**: This is the single most-viewed element on the page and the clearest one-for-one replacement opportunity — swapping the existing hand-rolled `SpendChart` for the new chart component directly improves the page's primary chart with the least redesign risk.

**Independent Test**: Load the Usage page with 30 days of spend history; confirm the spend trend renders as a chart with hover/inspection of individual day values, not a static row of bars with no interaction.

**Acceptance Scenarios**:

1. **Given** a user has spend history for the last 30 days, **When** they view the Usage page, **Then** the spend trend renders using the app's standard chart styling, and hovering or focusing a point shows that day's exact value.
2. **Given** a user has no spend in some days within the period, **When** they view the chart, **Then** those days are visibly represented as zero rather than omitted or visually indistinguishable from missing data.

### User Story 2 - Seeing cost breakdowns as charts, not just bars (Priority: P2)

A user wants to see how spend splits across plugins and agents, and how each call's tokens split between prompt and completion. Today this is a list of thin horizontal progress bars per item, plus a separate two-segment bar per item for the prompt/completion split. The user wants these breakdowns to read more like a proper chart-based comparison — for example, a bar or pie view for the overall plugin/agent split — while keeping the detailed per-item numbers.

**Why this priority**: This improves the page's two breakdown panels (by-plugin, by-agent) but is secondary to the primary trend chart — the existing progress-bar breakdown is functional today, just visually inconsistent with the new chart language.

**Independent Test**: Load the Usage page with spend spread across at least 3 plugins; confirm the plugin breakdown is presented with the same chart styling used elsewhere (e.g. a bar or pie chart of relative spend) rather than only plain progress bars.

**Acceptance Scenarios**:

1. **Given** spend is split across multiple plugins, **When** the user views the "By plugin" panel, **Then** the relative split is shown using the app's chart components, alongside (not necessarily replacing) the existing per-item numeric detail.
2. **Given** a single agent or plugin accounts for all spend, **When** the user views the breakdown, **Then** the chart still renders sensibly for a single-category case (no broken single-slice/single-bar rendering).

### User Story 3 - One consistent visual language across the whole page (Priority: P3)

A user viewing the Usage page today sees a mix of styles: hardcoded hex colors in the spend chart that don't match the app's theme tokens, a custom-built progress bar component, and the existing activity heatmap panel (a separate visualization style from phase 92) all next to each other. The user wants the whole page to feel like one coherent screen built from the same chart system, not a collection of separately hand-built widgets.

**Why this priority**: This is the overarching "whole screen rework" framing the user asked for, but it's naturally the last thing to land — it depends on User Stories 1 and 2 already having replaced the two biggest one-off visualizations, and is otherwise a consistency pass rather than new capability.

**Independent Test**: Review every visualization on the Usage page (spend trend, token split, plugin/agent breakdown, activity heatmap) and confirm none use hardcoded colors outside the app's theme tokens.

**Acceptance Scenarios**:

1. **Given** the Usage page is fully loaded, **When** a reviewer inspects each chart/visualization on the page, **Then** none use colors outside the app's defined theme tokens.
2. **Given** the Usage page and another chart-driven page (e.g. the memory graph's entity activity chart) are viewed together, **When** compared, **Then** they visually read as the same design system.

### Edge Cases

- What happens on a user's first day using Ze, with only one day of spend data? The spend trend chart must still render sensibly, not show a broken/empty 30-day chart.
- What happens when total spend is exactly zero for the whole period? Charts must show a clear "no spend yet" state rather than an empty-looking or misleading chart.
- What happens when there are many plugins or agents (more than fit comfortably in a small breakdown chart)? The breakdown chart must remain legible — grouping smaller categories or truncating gracefully rather than becoming unreadable.
- How do charts on this page behave at narrow widths (mobile or a resized window)? They must remain legible, consistent with the narrow-layout requirement established for charts generally.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Usage page's spend-over-time visualization MUST be rendered using the app's standard chart component, replacing the current hand-rolled implementation.
- **FR-002**: The spend trend chart MUST support inspecting an individual period's (e.g. a day's) exact value, not just its relative bar height.
- **FR-003**: Days or periods with zero spend MUST be visibly represented in the chart as zero, not omitted.
- **FR-004**: The plugin and agent spend breakdowns MUST include a chart-based view of relative proportions (e.g. bar or pie), in addition to existing per-item numeric detail — the numeric detail is not removed.
- **FR-005**: All charts and chart-like visualizations on the Usage page MUST use the app's theme color tokens — no hardcoded hex colors independent of the app's design system.
- **FR-006**: Every chart on the page MUST render a sensible state for edge cases: single data point, all-zero data, and a large number of breakdown categories — never a broken or blank render.
- **FR-007**: Charts on the Usage page MUST remain legible at narrow viewport widths, consistent with the narrow-layout requirement established for charts generally.
- **FR-008**: The existing per-item numeric detail (percentage, call count, token count, cost per call) in the plugin/agent breakdowns MUST remain available after the rework — the chart supplements this detail, it does not replace it.

### Key Entities

- **Daily Spend Series**: The existing per-day cost/call data already retrieved for the Usage page, now rendered through the chart component instead of a hand-rolled visualization — no new data.
- **Spend Breakdown**: The existing by-plugin and by-agent spend groupings, now additionally rendered as a chart-based proportion view alongside their current numeric list form — no new data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can identify their exact spend for any single day in the last 30 days by inspecting the chart, without needing to consult a separate table.
- **SC-002**: A user can identify which plugin or agent accounts for the largest share of spend within 5 seconds of viewing the breakdown panel, using the chart view.
- **SC-003**: Zero hardcoded colors remain in the Usage page's chart-rendering code — 100% of chart colors resolve through the app's theme tokens.
- **SC-004**: All visualizations on the Usage page render a valid, non-broken state across the tested edge cases (single day of data, zero spend, many breakdown categories), verified for 100% of cases exercised.
- **SC-005**: The Usage page passes the same visual-consistency review already applied to other redesigned pages, with reviewers unable to identify a visualization on the page as pre-dating the chart rework.

## Assumptions

- This feature builds directly on the chart primitives and styling delivered in spec 118-chart-visualization; it does not introduce new chart types beyond that starter set unless a specific need is identified during planning.
- The activity heatmap panel (phase 92, calendar-style heatmap) is a distinct visualization style not covered by the spec 118 starter set (line/bar/area/pie); this feature does not require replacing it, only ensuring the rest of the page around it is visually consistent. Replacing the heatmap itself is out of scope unless a heatmap chart type is added in a future phase.
- The underlying cost/usage data (daily spend, by-plugin, by-agent, token splits) already exists via the current Usage page's data source and does not require new backend aggregation — only new presentation.
- "The whole usage and data screen" refers to the existing `/costs` page (`CostsOverview` widget); it does not extend to other cost-related surfaces (e.g. per-message cost details) unless identified as in-scope during planning.
