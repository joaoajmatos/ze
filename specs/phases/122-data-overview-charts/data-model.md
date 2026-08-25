# Data Model: Data Overview Charts

No new persisted entities, no API changes. Two derived view-model mappings from data the page already fetches (`useDataDomainsQuery`).

## Category Chart Points

Derived from the existing `buildCategorySegments(domains, totalBytes): CategorySegment[]` (`apps/ze-web/src/widgets/data-overview/lib/aggregate.ts`), unchanged except the `color` field is no longer consumed by the renderer (research.md R2):

| `ChartPoint` field | Source |
|---|---|
| `x` | `CategorySegment.label` |
| `y` | `CategorySegment.bytes` |

## Domain Comparison Chart Points (per expanded group)

Derived from `groupByPrefix(domains)`'s existing per-group `DataDomainItem[]`, already sorted by size descending:

| `ChartPoint` field | Source |
|---|---|
| `x` | `shortDomainName(domain.name)` |
| `y` | `domain.size_bytes` |

## Relationships

- Both mappings are pure, render-only transformations of `useDataDomainsQuery`'s existing response and its existing `lib/aggregate.ts` helpers — no new query, no new backend field.
