# Feature Specification: Chart Visualization for UI and Agent Responses

**Feature Branch**: `118-chart-visualization`

**Created**: 2026-08-19

**Status**: Implemented

**Input**: User description: "Integrate Bklit UI (shadcn-registry chart component library) into Ze for both direct UI use and server-driven UI (SDUI). Scope: (1) install a starter set of Bklit chart components (line, bar, area — expandable later) into apps/ze-web via the shadcn CLI, for direct use in dashboard/analytics pages; (2) add a new "chart" pattern descriptor in core/ze-components (Python, mirroring existing patterns like patterns/metric.py) so agents can emit chart data via the existing @tool/pattern mechanism; (3) extend packages/ze-ui's schema (schema.ts/generated types) and PrimitiveRenderer to map the chart descriptor to the correct Bklit React component per chart_type, handling each chart type's distinct prop shape (not a single generic passthrough); (4) wire the new pattern into ze_components.tools the same way existing patterns are exposed to agents. Goal: agents can display data beautifully (charts) both as first-class UI components and as server-driven UI emitted from agent responses."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent shows a chart in the chat (Priority: P1)

While answering a user's question in conversation (e.g. "how has my spending trended this month?" or "show me my goal progress over time"), an agent decides that a chart communicates the answer better than prose or a table, and emits a chart as part of its response. The user sees a rendered, styled chart inline in the chat, matching the rest of the app's visual language, without any custom rendering logic having been written for that specific question.

**Why this priority**: This is the core value proposition — the ability for any agent to reach for a chart when data has a shape (trend, comparison, distribution) that is genuinely clearer visually than as text. Without this, the feature has no reason to exist.

**Independent Test**: Can be fully tested by having an agent emit a line chart and a bar chart for two different sample datasets in a conversation, and confirming both render correctly, styled consistently with the app, with no developer-written custom code for that specific chart instance.

**Acceptance Scenarios**:

1. **Given** an agent has time-series data relevant to its response (e.g. daily spend over 30 days), **When** it emits that data as a chart, **Then** the user sees a rendered line (or area) chart inline in the chat, with axis labels and a legend where applicable.
2. **Given** an agent has categorical comparison data (e.g. spend by category), **When** it emits that data as a chart, **Then** the user sees a rendered bar chart inline in the chat with readable category labels.
3. **Given** a chart is rendered in the chat, **When** the user views it on both a light and dark theme, **Then** the chart's colors and text remain legible and visually consistent with the rest of the app in both themes.

---

### User Story 2 - Developer adds a chart to a dashboard page (Priority: P2)

A developer building a Ze dashboard/analytics page (e.g. costs, activity heatmap, goal detail) wants to add a chart as a first-class page component, not as something emitted by an agent. They add a chart component to the page the same way they'd add any other UI building block in the app, styled consistently with the rest of the design system, without needing to hand-roll a charting solution or wire up a new third-party library from scratch.

**Why this priority**: Ze already has several dashboard-style pages (costs, activity heatmap, goal detail, workflow detail) that currently use ad-hoc or no charting. A reusable, consistent charting toolkit for hand-written UI is valuable on its own, independent of the agent-emission path, but is secondary to the agent-facing capability which is the feature's main driver.

**Independent Test**: Can be fully tested by adding a chart to one existing dashboard page and confirming it renders correctly and matches the app's visual language, independent of any agent or server-driven-UI code path.

**Acceptance Scenarios**:

1. **Given** a developer is building a page that needs to show a trend or comparison, **When** they add a chart component to that page, **Then** the chart renders using the same visual language (colors, typography, spacing) as the rest of the app's UI components.
2. **Given** the chart toolkit is installed, **When** a developer needs a chart type covered by the starter set (line, bar, area), **Then** they can use it without writing new low-level rendering or data-binding code.

---

### User Story 3 - Chart type coverage is extensible (Priority: P3)

A developer later wants to support a chart type not in the initial starter set (e.g. pie, radar, heatmap) because a new use case calls for it. They can add support for that chart type following the same pattern established for the starter set, without redesigning the underlying mechanism that lets agents emit charts or lets developers use them directly.

**Why this priority**: The initial set (line, bar, area) covers the most common "trend" and "comparison" cases well, but the value of choosing a broad charting toolkit is diminished if adding new chart types later requires rethinking the architecture. This is about protecting future extensibility, not delivering new user-facing value today.

**Independent Test**: Can be tested by adding one additional chart type beyond the starter set (e.g. pie) end-to-end — from agent-emittable descriptor through to rendered UI — and confirming it required only additive changes, not changes to how existing chart types work.

**Acceptance Scenarios**:

1. **Given** the starter set of chart types is implemented, **When** a new chart type is added later, **Then** existing chart types continue to render and behave exactly as before.

---

### Edge Cases

- What happens when an agent emits a chart descriptor for a chart type that isn't supported yet? The system must fail gracefully (e.g. a clear fallback or omission) rather than breaking the rest of the message rendering.
- What happens when an agent emits a chart descriptor with malformed, missing, or empty data (e.g. no data points, mismatched series lengths)? The user should see a sensible empty/error state, not a broken layout or a rendering crash.
- What happens when a chart is emitted with a very large number of data points (e.g. hundreds of days of daily data)? The chart must remain legible and performant, not overwhelm the chat layout.
- How does the system behave when a chart is rendered inside a narrow layout (e.g. mobile width, a side panel)? The chart must remain readable and not overflow or clip.
- What happens when chart data contains values an agent cannot reasonably know are safe to render as-is (e.g. arbitrary user-entered category labels)? Labels must render as inert text, not be interpreted as markup.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a starter set of chart types — at minimum line, bar, and area — usable both as directly-placed UI components on developer-built pages and as part of agent-emitted responses.
- **FR-002**: Agents MUST be able to include a chart in a response through the same general mechanism they already use to include other structured UI (e.g. cards, metrics, lists), without needing chart-type-specific bespoke code per use.
- **FR-003**: Each chart type MUST render with the data and shape appropriate to that type (e.g. a bar chart shows discrete categories, a line/area chart shows a data series over a continuous or ordered axis) — the system MUST NOT force all chart types through one generic, one-size-fits-all rendering path that ignores each type's distinct data shape.
- **FR-004**: Charts rendered in the product MUST visually match the rest of the app's design system (color palette, typography, spacing) in both light and dark themes.
- **FR-005**: When an agent emits a chart descriptor whose chart type is not (yet) supported, the system MUST degrade gracefully — the surrounding response must still render, with the unsupported chart omitted or replaced by a clear fallback, not a rendering failure.
- **FR-006**: When chart data is missing, empty, or malformed, the system MUST show a sensible empty/error state rather than an unhandled crash or a visually broken layout.
- **FR-007**: Chart labels and text values that originate from user or external data MUST be rendered as inert text, never interpreted as executable markup.
- **FR-008**: The mechanism for adding a new chart type MUST be additive — introducing a new chart type MUST NOT require changing the behavior or rendering of existing chart types.
- **FR-009**: Charts MUST remain legible and usable across the range of layout widths the product already supports (e.g. full-width dashboard pages down to a narrow side panel).
- **FR-010**: Developers building dashboard/analytics pages MUST be able to place a chart from the starter set directly into a page's UI without going through the agent-response path.

### Key Entities

- **Chart Descriptor**: A structured, serializable description of "a chart to render" — carries a chart type (e.g. line, bar, area), the data/series to plot, and presentational metadata (e.g. labels, legend). Produced by agents as part of a response, or used directly by developers when building a page.
- **Chart Type**: One member of the supported set of visual chart forms (line, bar, area, and others added later), each with its own expected data shape and rendering behavior.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An agent can include a chart in a chat response, and a user sees it rendered correctly, for at least 3 distinct chart types (line, bar, area), with no per-conversation custom development work.
- **SC-002**: A developer can add any of the 3 starter chart types to a new or existing dashboard page in under 15 minutes of hands-on work, without writing new low-level charting logic.
- **SC-003**: 100% of chart types in the starter set render legibly (no clipped text, no unreadable overlaps) at both a full-width dashboard layout and the narrowest supported panel width, in both light and dark theme.
- **SC-004**: Adding a new chart type beyond the starter set requires changes only to code that is additive (new files/new cases), with zero regressions in existing chart types' rendering, verified by existing coverage continuing to pass unchanged.
- **SC-005**: When given malformed or unsupported chart input, the system produces a graceful fallback in 100% of tested cases — never a full response-render failure.

## Assumptions

- The product already has an established design system (colors, typography, light/dark theming) that charts are expected to visually match, rather than defining a new one.
- The starter set of three chart types (line, bar, area) covers the majority of near-term use cases (trends over time, category comparisons); broader chart-type coverage (pie, radar, heatmap, etc.) is deferred and treated as future, additive work per User Story 3.
- Agents decide *when* a chart is the right way to communicate a piece of data; this feature is responsible for making that possible and rendering it well, not for prescribing which specific answers should become charts.
- A third-party, design-system-compatible charting component library is used as the underlying rendering technology rather than a from-scratch charting implementation, consistent with how other UI building blocks in the product are sourced.
- Both the developer-facing (hand-placed) and agent-facing (server-driven) usage paths share the same underlying chart rendering components, so visual consistency between the two is inherent rather than separately maintained.
- Chart data volume in the initial scope is bounded to what's reasonable for a chat response or a single dashboard panel (tens to low hundreds of data points); large-scale/streaming visualization is out of scope.
