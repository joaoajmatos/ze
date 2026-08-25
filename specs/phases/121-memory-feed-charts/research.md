# Research: Memory Feed Charts

## R1. Chart source

**Decision**: Reuse spec 118's `LineChart`/`BarChart`/`PieChart` from `packages/ze-ui/src/charts` directly in `apps/ze-web/src/pages/brain-memory/ui/BrainMemoryPage.tsx` (or a new small widget it composes) — growth-over-time is a `LineChart`/`BarChart` case, facts-vs-episodes composition is a `PieChart` case.

## R2. Growth-over-time data already exists

**Finding**: `GET /api/v0/memory/activity` (`get_memory_activity`, `core/ze-memory/ze_memory/admin.py:185`) already unions `memory_facts` + `memory_episodes` counts per day into `MemoryActivityDay{date, count}` — exactly what User Story 1's growth chart needs, no new query.

**Decision**: Feed `MemoryActivityResponse.days` directly into the growth chart (`{x: date, y: count}`) — reuse the existing `useMemoryActivityQuery` the page already calls for the `TimelineScrubber`'s density strip.

## R3. Composition (facts vs episodes) data gap

**Finding**: `get_memory_activity`'s SQL already unions `memory_facts` and `memory_episodes` per-day counts via `UNION ALL`, but collapses them into one `count` before the final `GROUP BY day` — the fact/episode split is computed and then immediately thrown away.

**Decision**: Change the query to `GROUP BY day, source` (adding a `source` label to each half of the union), then shape the result server-side into `MemoryActivityDay{date, count, fact_count, episode_count}` — two new additive fields, same endpoint, same existing call sites unaffected (they only read `count`/`date` today). The composition chart (User Story 2) sums `fact_count`/`episode_count` across the currently-loaded date range.

**Alternatives considered**:
- **A separate `/memory/composition` endpoint** — rejected: the data is already computed inside `get_memory_activity`'s query; a second endpoint would duplicate the same UNION for no benefit.
- **Client-side derivation from the feed list** — rejected: the feed list is paginated (phase 88), so a client-side total would be wrong for any account with more history than one page.

## R4. As-of (time-travel) consistency gap

**Finding**: `BrainMemoryPage.tsx` already tracks `asOfDate` for its time-travel scrubber, but its `useMemoryActivityQuery(earliest, earliest ? now : undefined)` call always queries `earliest → now` — it does **not** currently pass `asOfDate` as the upper bound, so the activity data (and thus the `TimelineScrubber`'s own density strip) already always reflects live "now" regardless of scrub position. This is a pre-existing inconsistency, not something this feature introduces, but FR-003 requires the *new* charts to get it right.

**Decision**: When implementing the new charts, change the query call to `useMemoryActivityQuery(earliest, asOfDate ?? now)` so both the new charts and the existing scrubber strip consistently reflect the as-of state. This is a one-line fix to an existing call site, not a new capability — flagging it explicitly since it's a small pre-existing bug this feature's correctness depends on fixing.

## R5. Placement

**Decision**: Add both charts as a new small panel above the `TimelineScrubber` (or directly beside it) in `BrainMemoryPage.tsx`, consistent with where the page already surfaces time-oriented context, rather than inside the `MemoryFeed` list widget itself (which is a per-item list, not a page-level summary).
