# Research: Data Overview Charts

## R1. Chart source

**Decision**: Reuse spec 118's `PieChart`/`BarChart` from `packages/ze-ui/src/charts` directly in `apps/ze-web/src/widgets/data-overview`. Category breakdown is a `PieChart` case (replacing `StorageDonutChart` 1:1); domain-within-group comparison is a `BarChart` case.

## R2. Replacing `StorageDonutChart`

**Finding**: `StorageDonutChart.tsx` is a hand-rolled `<svg>` `<circle>` stroke-dasharray donut with a fixed `CATEGORY_COLORS` palette (`rgba(128,82,255,0.9)`, etc. — already reasonably close to theme hues but defined independently, not through `--color-*` tokens) and its own legend rows. `buildCategorySegments()` (`../lib/aggregate.ts`) already does the useful aggregation work this feature needs to keep: grouping by category prefix and folding anything under a 2%-of-total threshold into an "other" bucket (already solving FR-005's "many categories" edge case).

**Decision**: Delete `StorageDonutChart.tsx`'s custom SVG rendering; keep `buildCategorySegments()` as-is (it already returns `{label, bytes, color}[]`, trivially mapped to `ChartPoint[]` via `{x: label, y: bytes}`); render via `packages/ze-ui`'s `PieChart`, dropping the segment-level `color` override since `PieChart` already assigns colors from the shared `--chart-1..5` palette (spec 118) — consistent with FR-004 (theme tokens only).

**Alternatives considered**: Keep `buildCategorySegments()`'s manual `color` assignment and pass it through as `PieChart`'s per-point color override — rejected as the default: spec 118's `PieChart` wrapper already cycles the shared palette automatically; passing manual colors would reintroduce a second, parallel color source instead of removing one (against FR-004's "zero hardcoded colors" intent, even though these particular ones aren't hex-hardcoded, just independently defined).

## R3. Domain comparison within a group

**Finding**: `DataOverview.tsx`'s `BreakdownPanel`/`BreakdownGroup` already groups domains by prefix (`groupByPrefix()`) and sorts by size descending; each `DomainBreakdownItem` renders a `MetricProgressBar` (single-value % bar) per domain.

**Decision**: Add a `BarChart` inside each `BreakdownGroup`, above the existing `DomainBreakdownItem` list, mapping each group's domains to `{x: shortDomainName(domain.name), y: domain.size_bytes}` — additive, existing per-domain `MetricProgressBar`/numeric detail stays (FR-003).

## R4. Empty-state handling

**Finding**: `StorageDonutChart` already has a custom empty state (`totalBytes === 0 || segments.length === 0`) with its own "No data" placeholder markup, independent of spec 118's `PieChart` empty-state (`EmptyChart` in `packages/ze-ui/src/charts/index.tsx`).

**Decision**: Drop the custom empty-state markup and rely on spec 118's `PieChart`'s built-in empty state (`data: []` → `EmptyChart`) — one less bespoke empty-state implementation to maintain, consistent behavior with every other chart in the app.
