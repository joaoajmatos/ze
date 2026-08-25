# Feature Specification: Memory Graph Charts

**Feature Branch**: `119-memory-graph-charts`

**Created**: 2026-08-19

**Status**: Implemented

**Input**: User description: "Improve Ze's memory graph visualization. Context: phase 94 shipped GET /api/v0/memory/graph + a React Flow-based entity/relationship graph at /brain/graph (click-to-expand neighbourhoods, dagre layout). The user says \"memory should have better graphs\" and wants this reworked using the new chart-visualization capability just shipped in spec 118-chart-visualization (core/ze-components Chart/ChartPoint primitive, packages/ze-ui chart renderer with line/bar/area/pie via Bklit, apps/ze-web/packages/ze-ui/src/charts). Scope should cover: what's actually weak about the current memory graph view today (visual density, lack of trend/activity context alongside the entity graph, styling consistency with the rest of the app), and how the new chart primitives could supplement or improve it — e.g. activity-over-time charts for an entity, relationship-strength/confidence visualizations, or better visual hierarchy. This is a UI/UX-focused improvement to an existing feature, not a new subsystem."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understanding an entity's activity at a glance (Priority: P1)

A user clicks an entity node in the memory graph (a person, place, org, or topic) and wants to understand not just *what* Ze knows about it, but *how that knowledge has built up over time* — is this a person who comes up constantly, or someone mentioned once months ago? Today the entity detail panel only shows a flat list of facts and episode summaries with no sense of recency or frequency. The user wants a small chart showing activity (mentions, facts learned, episodes) over time for the selected entity, right in the detail panel.

**Why this priority**: This is the single biggest, most concrete gap in the current experience — the detail panel already exists and is the natural place a chart adds the most value with the least disruption. It doesn't require touching the graph canvas itself.

**Independent Test**: Select an entity with activity spread across multiple time periods; confirm a chart in the detail panel shows that activity distributed over time, distinct from the flat facts/episodes lists.

**Acceptance Scenarios**:

1. **Given** a user selects an entity with facts and episodes recorded across several weeks, **When** the entity detail panel opens, **Then** a chart shows that entity's activity over time alongside the existing facts and episodes lists.
2. **Given** a user selects an entity with only one or two data points, **When** the detail panel opens, **Then** the chart still renders sensibly (no broken/empty-looking chart) or is omitted gracefully when there isn't enough data to show a trend.

---

### User Story 2 - Seeing the graph's composition, not just its shape (Priority: P2)

A user opens `/brain/graph` and sees an entity/relationship node graph, but has no quick way to answer "what kinds of things does Ze mostly know about me?" (mostly people? mostly topics?) or "which relation types dominate?" without manually counting nodes and edges. The user wants an at-a-glance breakdown — e.g. entity-type or relationship-type composition — visible on the graph page itself, using the same chart styling as the rest of the app.

**Why this priority**: Valuable but secondary to the per-entity activity view — it's about orienting the user in the graph as a whole, which matters most once the graph has enough nodes to be hard to read visually, whereas User Story 1 helps immediately for any single entity.

**Independent Test**: Open the graph page with a graph containing multiple entity types and relation types; confirm a composition chart is visible and its proportions match what's actually in the loaded graph.

**Acceptance Scenarios**:

1. **Given** the memory graph is loaded with a mix of entity types, **When** the user views the graph page, **Then** a chart shows the proportion of entity types (or relationship types) present in the current view.
2. **Given** the user expands the graph (loads more neighbours), **When** new entities are added to the view, **Then** the composition chart updates to reflect the expanded set.

---

### User Story 3 - A visually consistent, less dense graph page (Priority: P3)

A user finds the current graph canvas visually dense and inconsistent with the rest of Ze's redesigned "Open Sky" visual language (per spec 117), especially compared to pages that now use the new chart components. The user wants the graph page's non-graph chrome (toolbar, search, detail panel) to match the app's current design system, and wants unnecessary visual noise reduced so the graph itself is easier to read.

**Why this priority**: This is a polish pass with real but lower-urgency value — it improves the page's feel but doesn't unlock new understanding the way User Stories 1 and 2 do, and can be done last without blocking either.

**Independent Test**: Compare the graph page's toolbar, search bar, and detail panel styling against another already-redesigned page (e.g. the costs/usage page); confirm consistent colors, spacing, and typography.

**Acceptance Scenarios**:

1. **Given** the graph page and another redesigned dashboard page are viewed side by side, **When** comparing chrome elements (buttons, panels, labels), **Then** they use the same visual language (color tokens, spacing, typography).

---

### Edge Cases

- What happens when an entity has activity data but all of it falls on a single date (no real "trend" to show)? The chart must still render without looking broken (e.g. a single bar/point, not a blank error state).
- What happens when the graph view is empty (no entities loaded yet, or a search returns nothing)? Any composition chart must show a clear empty state rather than a chart rendering with no visible data.
- How does the activity chart behave for an entity with a very long history (months or years of activity)? It must remain legible rather than becoming an unreadable wall of bars/points.
- What happens when the user is on a narrow viewport (e.g. resized detail panel)? Charts in the detail panel must remain readable at reduced width, consistent with spec 118's narrow-layout requirement.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The entity detail panel MUST show a chart of the selected entity's activity over time (facts/episodes/mentions), in addition to the existing flat facts and episodes lists.
- **FR-002**: The activity chart MUST update when a different entity is selected, showing that entity's own activity history.
- **FR-003**: When an entity has too little activity data to show a meaningful trend (e.g. a single data point), the system MUST still render a sensible chart state or omit the chart gracefully — never a broken or visually empty chart.
- **FR-004**: The memory graph page MUST show a composition breakdown (e.g. by entity type and/or relationship type) of the entities and relationships currently loaded in the graph view.
- **FR-005**: The composition breakdown MUST reflect the current state of the loaded graph — it MUST update when the user expands the graph to include more entities.
- **FR-006**: All new charts on the memory graph page and in the entity detail panel MUST use the same chart styling (colors, typography, theming) already established for charts elsewhere in the app.
- **FR-007**: The memory graph page's non-graph UI (toolbar, search bar, detail panel chrome) MUST be visually consistent with the app's current design system, matching the visual language used on other already-redesigned pages.
- **FR-008**: Charts on the memory graph page and in the entity detail panel MUST remain legible when the detail panel is narrow (consistent with the narrow-layout requirement established for charts generally).
- **FR-009**: When the graph view has no data (empty search result, no entities loaded), any composition chart MUST show a clear empty state rather than an empty or misleading chart.

### Key Entities

- **Entity Activity Series**: A time-distributed view of one entity's associated facts, episodes, or mentions — the data behind the detail panel's new activity chart. Derived from data already retrievable per entity (facts, episodes), not a new stored concept.
- **Graph Composition Breakdown**: A summary of the currently loaded graph's entities and relationships, grouped by type — the data behind the graph page's new composition chart. Derived from the entities/edges already present in the loaded graph view, not separately persisted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can determine, within 5 seconds of opening an entity's detail panel, whether that entity's activity is recent/frequent or old/rare, using the new activity chart — without reading through the full facts/episodes lists.
- **SC-002**: A user can determine the dominant entity type or relationship type in the currently loaded graph within 5 seconds of viewing the graph page, without manually counting nodes.
- **SC-003**: 100% of entities selected in the detail panel — regardless of how little or much activity data they have — show either a sensible chart or a clear "not enough data" state, never a broken render.
- **SC-004**: The graph page's toolbar, search bar, and detail panel pass the same visual-consistency review already applied to other redesigned pages (matching color tokens, spacing, typography), with zero one-off styling left over from the pre-118 look.

## Assumptions

- This feature builds directly on the chart primitives and styling delivered in spec 118-chart-visualization; it does not introduce new chart types beyond that starter set unless a specific need is identified during planning.
- The underlying data needed for the activity chart (per-entity facts/episodes with timestamps) and the composition breakdown (entity/relationship types already present in `GET /api/v0/memory/graph` and entity-detail responses) already exists and does not require new backend storage — only new aggregation/shaping of existing data.
- The graph canvas itself (React Flow + dagre layout, click-to-expand behavior) is out of scope for replacement; this feature adds charts alongside it and restyles its surrounding chrome, it does not redesign the node-graph interaction model.
- "Better graphs" is interpreted as: richer per-entity insight (User Story 1), better at-a-glance orientation in the whole graph (User Story 2), and visual consistency (User Story 3) — not a request to replace the entity/relationship graph with charts.
