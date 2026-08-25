# Feature Specification: Memory Feed Charts

**Feature Branch**: `121-memory-feed-charts`

**Created**: 2026-08-19

**Status**: Implemented

**Input**: User description: "Rework the Memory page (/brain-memory) using the new chart suite. Context: the page today shows a search/filter bar, a TimelineScrubber (a mini per-day activity density strip used for time-travel scrubbing), and a reverse-chronological feed list of facts/episodes (phase 88/93). There is no chart showing memory growth or composition (facts vs episodes) over time — only the raw feed and the scrubber's density strip. This is one of 4 screens (Memory, Graph, Data, Usage) being reworked with the chart-visualization capability from spec 118-chart-visualization."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Seeing how memory has grown over time (Priority: P1)

A user opens the Memory page and wants to understand, at a glance, how much Ze has learned and when — is memory growing steadily, did it spike after a big conversation, has it gone quiet recently? Today the only signal is the `TimelineScrubber`'s density strip (a scrubbing control, not really a readable chart) and the raw feed list itself. The user wants a proper chart showing memory volume (facts + episodes) accumulated or recorded over time.

**Why this priority**: This is the core "make sense of my memory at a glance" gap — the feed list is detail-first, and the scrubber is a navigation control, not an insight surface. A dedicated chart is the most direct fix.

**Independent Test**: Load the Memory page for a user with memory activity spread across multiple weeks; confirm a chart shows that activity distributed over time, distinct from the scrubber strip and the feed list.

**Acceptance Scenarios**:

1. **Given** a user has facts and episodes recorded across several weeks, **When** they open the Memory page, **Then** a chart shows memory volume over time.
2. **Given** the user scrubs to an earlier point in time via the `TimelineScrubber` (time-travel view), **When** the page updates to that historical state, **Then** the chart reflects the memory that existed as of that point, consistent with the rest of the page's time-travel behavior.

---

### User Story 2 - Understanding what kind of memory dominates (Priority: P2)

A user wants to know whether Ze's memory of them is mostly durable facts or mostly narrative episodes, without manually counting entries in the feed or relying on the "Facts"/"Episodes"/"All" filter chips to estimate proportions. The user wants a simple composition view (facts vs episodes) presented as a chart.

**Why this priority**: Useful orientation, but secondary to the growth-over-time view — it answers a narrower question and the existing filter chips already provide a rough manual way to check this today.

**Independent Test**: Load the Memory page with a mix of facts and episodes; confirm a chart shows their relative proportion, matching what filtering the feed to each type would show.

**Acceptance Scenarios**:

1. **Given** a user has both facts and episodes recorded, **When** they view the Memory page, **Then** a chart shows the proportion of facts vs episodes.
2. **Given** a user has only one type recorded (e.g. only facts, no episodes yet), **When** they view the chart, **Then** it still renders sensibly rather than showing a broken or empty chart.

---

### Edge Cases

- What happens for a brand-new user with only a day or two of memory? The growth chart must still render sensibly (not a broken/empty 30+ day chart).
- What happens when a user has zero facts or zero episodes (not both, just one type entirely absent)? The composition chart must show a clear single-category state, not an error.
- How do the new charts behave while the page is in "time travel" mode (viewing an earlier `as_of` date)? They must reflect the same as-of state as the rest of the page, not silently show current-day data.
- How do these charts behave at narrow viewport widths? They must remain legible, consistent with the narrow-layout requirement established for charts generally.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Memory page MUST show a chart of memory volume (facts and/or episodes) over time, distinct from the existing `TimelineScrubber` density strip and the feed list.
- **FR-002**: The Memory page MUST show a chart of the composition of memory by type (facts vs episodes).
- **FR-003**: When the user is viewing an earlier point in time via the timeline scrubber, both new charts MUST reflect that same as-of state, not the current live state.
- **FR-004**: Both new charts MUST use the app's theme color tokens and existing chart styling — no hardcoded, one-off colors.
- **FR-005**: Both new charts MUST render a sensible state when data is sparse (new user, single type only) or absent — never a broken or blank render.
- **FR-006**: Both new charts MUST remain legible at narrow viewport widths, consistent with the narrow-layout requirement established for charts generally.
- **FR-007**: The existing search, filter chips, timeline scrubber, and feed list MUST continue to work exactly as before — this feature adds charts, it does not remove or replace existing functionality.

### Key Entities

- **Memory Growth Series**: A time-distributed count of facts and episodes recorded, up to the currently selected as-of date — the data behind the new growth chart. Derived from data already retrievable for the feed and timeline-bounds/activity endpoints, not a new stored concept.
- **Memory Type Composition**: A count of facts vs episodes, as of the currently selected as-of date — the data behind the new composition chart. Derived from the same underlying feed data, not separately persisted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can tell whether their memory has been growing steadily or in bursts within 5 seconds of opening the Memory page, without reading through the feed list.
- **SC-002**: A user can tell whether their memory is mostly facts or mostly episodes within 5 seconds of opening the Memory page.
- **SC-003**: 100% of time-travel scrub actions update both new charts to match the selected as-of state, with zero cases of the charts showing stale (current-day) data while the rest of the page shows historical data.
- **SC-004**: Both new charts render a valid, non-broken state across tested edge cases (new user with minimal data, single-type-only data), verified for 100% of cases exercised.

## Assumptions

- This feature builds directly on the chart primitives and styling delivered in spec 118-chart-visualization; it does not introduce new chart types beyond that starter set unless a specific need is identified during planning.
- The underlying data (per-day fact/episode counts, type breakdown, as-of-date filtering) already exists via the Memory page's current data sources (feed, timeline-bounds, activity queries) and does not require new backend storage — only new aggregation/shaping of existing data.
- The existing `TimelineScrubber` control itself is not replaced by this feature — it remains the primary time-travel navigation control; the new charts are additive context alongside it.
