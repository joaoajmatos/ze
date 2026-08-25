# Research: Usage Dashboard Charts

## R1. Chart source

**Decision**: Reuse spec 118's `LineChart`/`BarChart`/`PieChart` from `packages/ze-ui/src/charts` directly in `apps/ze-web/src/widgets/costs-overview/ui/CostsOverview.tsx`, exactly as the spec-118 `CostsPage` demo already proved out (`apps/ze-web/src/pages/costs/ui/CostsPage.tsx`).

**Rationale**: No new chart type needed — spend-over-time is a `LineChart`/`AreaChart`/`BarChart` case (daily buckets, already time-series shaped via `DailyCostBucket.date`), and plugin/agent proportion is a `BarChart`/`PieChart` case.

## R2. Replacing `SpendChart`

**Finding**: `SpendChart` (`CostsOverview.tsx:98-147`) is a hand-rolled `<svg>` of `<rect>` bars — no axis, no legend, no hover/tooltip, hardcoded fill colors (`"#ffb829"`, `"rgba(128,82,255,0.9)"`, etc.) independent of `--color-amber-spark`/`--color-plum-voltage`. It already does one useful thing spec 118's raw `LineChart`/`BarChart` don't: `fillDays()` zero-fills missing days so gaps are visible (FR-003 in this spec).

**Decision**: Replace `SpendChart` with `packages/ze-ui`'s `BarChart` (daily granularity reads better as bars than a line for spend, matching the "compare distinct days" nature of the data), keeping `fillDays()` as pre-processing before mapping `DailyCostBucket[]` → `ChartPoint[]` (`{x: date, y: usd}`). This satisfies FR-001–FR-003 without touching data-fetching.

**Alternatives considered**: `LineChart`/`AreaChart` — viable, but a 30-bar comparison reads more naturally as discrete bars than a continuous line for a "$/day" quantity; deferred to implementation-time visual judgment, not a hard requirement.

## R3. Replacing `TokenSplit` and adding breakdown charts

**Finding**: `TokenSplit` (`CostsOverview.tsx:149-173`) is a two-segment mini progress bar (prompt vs completion %) per breakdown item — not itself a candidate for the starter chart set (no 2-segment "split bar" chart type exists in spec 118, and this is a per-item micro-visualization, not a page-level chart). The by-plugin/by-agent breakdown panels (`UsageItem`, `BreakdownPanel`) are lists of full-width progress bars, one per plugin/agent.

**Decision**: Add one `PieChart` with `donut` above each of the "By plugin" and "By agent" `BreakdownPanel`s, showing relative spend share as a ring rather than a solid pie — additive, alongside the existing `UsageItem` list (FR-004, FR-008). A ring leaves room for a center label (e.g. total spend for that breakdown) and reads as less visually heavy than a solid pie when placed above a list of the same categories. `packages/ze-ui`'s `PieChart` gained a `donut?: boolean` prop for exactly this (updates spec 118's shipped component, additive — see its `packages/ze-ui/src/charts/index.tsx`). Fall back to `BarChart` at implementation time only if a given breakdown routinely has more categories than a ring stays legible for (research.md's own "many categories" edge case, FR-006). `TokenSplit` is left as-is: it's a compact per-row detail, not a page-level chart — replacing it is out of scope per this spec's Assumptions.

**Alternatives considered**: Replacing `TokenSplit` with a tiny inline `PieChart` per row — rejected: `PieChart`'s minimum legible size (spec 118 renders it via `ParentSize`, expects real chart real estate) doesn't fit a single-row micro-visualization; forcing it in would look worse, not better.

## R4. Hardcoded colors sweep (FR-005)

**Finding**: Beyond `SpendChart`'s fills, `AnomalyPanel`'s dot (`bg-lichen`) and border/bg (`border-amber-spark/20`, `bg-amber-spark/[0.04]`) already use theme tokens correctly — the hardcoded-hex problem is isolated to `SpendChart`. `TokenSplit`'s colors (`bg-plum-voltage/70`, `bg-foreground/15`) are also already token-based.

**Decision**: FR-005's "zero hardcoded colors" scope is effectively just `SpendChart`'s three inline hex/rgba fills — removing that one file's custom SVG removes the hardcoded colors as a side effect of R2, not a separate sweep.

## R5. Activity heatmap panel

**Decision** (confirmed, matches spec's Assumptions): `ActivityHeatmapPanel` (phase 92) stays as-is — heatmap isn't in spec 118's starter chart set. Only ensure it visually sits well next to the new charts (spacing/panel chrome), not a rebuild.
