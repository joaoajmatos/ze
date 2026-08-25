# Contract: `MemoryActivityDay` gains `fact_count` / `episode_count`

## Before

```json
{ "date": "2026-07-02", "count": 5 }
```

## After

```json
{ "date": "2026-07-02", "count": 5, "fact_count": 3, "episode_count": 2 }
```

**Backward compatibility**: Additive only. `date`/`count` semantics unchanged — the `TimelineScrubber`'s existing density strip (`apps/ze-web/src/widgets/timeline-scrubber`) keeps working unmodified since it only reads `count`.

**Source**: `core/ze-memory/ze_memory/admin.py:185` `get_memory_activity` — change the inner `UNION ALL` to label each half (`'fact'`/`'episode'` as a `source` column), `GROUP BY day, source` instead of collapsing immediately, then fold the per-source rows into one dict per day in Python (`{date, count: fact_count + episode_count, fact_count, episode_count}`). `apps/ze-api/ze_api/api/schemas.py:859` `MemoryActivityDay` gains the two new required int fields.

## Also in scope: as-of wiring (not a contract change, a call-site fix)

`apps/ze-web/src/pages/brain-memory/ui/BrainMemoryPage.tsx`'s existing `useMemoryActivityQuery(earliest, earliest ? now : undefined)` call changes its second argument to `asOfDate ?? now`, so the endpoint's existing `end` parameter reflects the page's time-travel state (research.md R4). No endpoint signature change — `start`/`end` already exist as query params.
