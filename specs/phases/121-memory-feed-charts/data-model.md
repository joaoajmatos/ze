# Data Model: Memory Feed Charts

## `MemoryActivityDay` (backend schema change)

`apps/ze-api/ze_api/api/schemas.py` (or wherever `MemoryActivityDay` is defined) — add two fields, keep `date`/`count` unchanged for existing consumers:

| Field | Type | Change |
|---|---|---|
| `date` | `str` | unchanged |
| `count` | `int` | unchanged (still `fact_count + episode_count`, for the `TimelineScrubber`'s existing density strip) |
| `fact_count` | `int` | **new** |
| `episode_count` | `int` | **new** |

`core/ze-memory/ze_memory/admin.py`'s `get_memory_activity` query changes from a collapsing `UNION ALL ... GROUP BY day` to a labeled union grouped by `(day, source)`, then reshaped in Python into the three-count-per-day dict.

## Growth Chart Points (frontend, derived)

| `ChartPoint` field | Source |
|---|---|
| `x` | `MemoryActivityDay.date` |
| `y` | `MemoryActivityDay.count` |

## Composition Chart Points (frontend, derived)

Summed across the currently-loaded `MemoryActivityResponse.days` (respecting the as-of upper bound, research.md R4):

| `ChartPoint` field | Source |
|---|---|
| `x` | `"Facts"` / `"Episodes"` |
| `y` | `sum(day.fact_count)` / `sum(day.episode_count)` |

## Relationships

- Both chart point sets derive from one existing endpoint's response (`GET /api/v0/memory/activity`), now returning two additional additive fields — no new query, no new persisted concept.
