# Data Model: Usage Dashboard Charts

No new persisted entities, no API changes. Two derived view-model mappings from data the page already fetches (`useCostsQuery`).

## Daily Spend Chart Points

Derived in `CostsOverview.tsx` from `WebCostSummaryResponse.by_day: DailyCostBucket[]`, reusing the existing `fillDays()` zero-fill helper:

| `ChartPoint` field | Source |
|---|---|
| `x` | `DailyCostBucket.date` |
| `y` | `DailyCostBucket.usd` |

## Plugin / Agent Breakdown Chart Points

Derived from `WebCostSummaryResponse.by_plugin` / `by_agent` (`Record<string, UsageStats>`), the same data already sorted into `sortedPlugins`/`sortedAgents`:

| `ChartPoint` field | Source |
|---|---|
| `x` | Plugin or agent key (formatted via existing `formatPluginName`/`formatAgentName`) |
| `y` | `usage.usd` |

## Relationships

- Both mappings are pure, render-only transformations of `useCostsQuery`'s existing response — no new query, no new backend field, no persistence.
