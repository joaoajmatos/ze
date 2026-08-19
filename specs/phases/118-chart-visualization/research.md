# Research: Chart Visualization for UI and Agent Responses

## R1. Chart component source

**Decision**: Use Bklit UI (`https://bklit.com/docs/installation`) as the chart component source, installed per-component via the shadcn CLI (`pnpm dlx shadcn@latest add @bklit/<chart>`) into `apps/ze-web`.

**Rationale**: Bklit ships 17 shadcn-registry chart types (including the starter set: line, bar, area) as owned source code — not an npm runtime dependency — matching how `apps/ze-web/src/shared/ui/primitives/{button,input,sheet,slider}.tsx` were already sourced. Owned source means the components can be re-themed to Ze's design tokens directly, with no version-locked black box.

**Alternatives considered**:
- **Recharts directly** (Bklit's own underlying dependency) — rejected: would require hand-building every chart type's composition (axes, tooltip, legend, responsive container) that Bklit already provides pre-composed.
- **A full JS charting library** (Chart.js, ApexCharts, Nivo) — rejected: introduces a second design language and a runtime dependency with its own theming system, working against FR-004 (visual match to the app).
- **Hand-rolled SVG charts** — rejected: reasonable only for 1-2 chart types; doesn't scale to User Story 3's extensibility goal and reinvents axis/tooltip/legend primitives Bklit already solves.

## R2. shadcn CLI bootstrap state

**Finding**: `apps/ze-web` has no `components.json` — the shadcn CLI has never actually been run in this repo. The existing shadcn-style primitives (`button.tsx`, `input.tsx`, `sheet.tsx`, `slider.tsx`) were hand-authored/adapted to match Ze's Tailwind v4 `@theme` tokens, not installed via `shadcn add`.

**Decision**: Bootstrap a minimal `components.json` scoped to `apps/ze-web` (pointing its `tailwind.css` at `src/app/styles/globals.css`, aliases at the existing `shared/ui` paths, `cn` at `shared/lib/cn`) so `shadcn add @bklit/<chart>` can run non-interactively. Immediately after each `add`, hand-adapt the generated component's className usage to Ze's existing token names (see R3) the same way the current primitives were adapted — the CLI is a source-fetch mechanism here, not a hands-off installer.

**Rationale**: The CLI is still the fastest correct way to pull each chart's component + its Radix/Recharts sub-dependencies in one step; bootstrapping the config once is cheaper than manually recreating what the CLI would fetch, and doesn't preclude the manual re-theming pass that's required either way (see R3).

**Alternatives considered**:
- **Copy component source by hand from the Bklit docs site** — rejected as primary path (no CLI dependency resolution for `recharts`), but remains the fallback if the registry endpoint the CLI hits is unreachable from this environment.

## R3. Theming — matching Bklit charts to Ze's "Open Sky" palette

**Finding**: `apps/ze-web/src/app/styles/globals.css` already defines the full shadcn semantic token set Tailwind v4-style (`--color-background`, `--color-primary`, `--color-border`, etc. under `@theme`) — see the "shadcn semantic aliases" block. Bklit's chart components, being shadcn-registry components, are written against these same token names, so base chrome (axes, grid, tooltip surface, borders) should theme correctly with no changes.

**Gap**: Multi-series chart color (the `--chart-1` … `--chart-5` CSS variables Bklit/shadcn chart components read for series colors) is **not** defined in `globals.css` today — only single-accent tokens (`--color-primary`, `--color-success`, `--color-warning`, `--color-lichen`, `--color-amber-spark`, `--color-plum-voltage`, `--color-ember`) exist.

**Decision**: Add a `--chart-1` through `--chart-5` scale to `globals.css`, built from the existing "Open Sky" palette (plum-voltage, amber-spark, lichen, ember, plus one new tinted-neutral) rather than introducing new hues, so agent-emitted and developer-placed charts both inherit the same look with zero per-chart color configuration (supports FR-004, SC-003).

**Alternatives considered**:
- **Pass explicit colors per chart instance** — rejected as the default: defeats "styled consistently... without hand-written custom rendering logic" (User Story 1); still allowed as an optional override field on the descriptor for cases that need it (e.g. semantic red for an over-budget series), not the default path.

## R4. Server-driven UI wiring pattern for a "chart" descriptor

**Finding**: `core/ze-components` follows a consistent 3-layer pattern per existing pattern (e.g. `patterns/metric.py`): (1) a private LLM-facing schema dataclass in `ze_components/tools.py` (e.g. `_MetricSchema`), (2) a `render_tool`-decorated async function registered as a `@tool`, and (3) the actual returned `Primitive` tree assembled from `atoms`/`molecules`. `packages/ze-ui` mirrors every primitive as a generated TS type (`generated/types.gen.ts`) and a `case` arm in `PrimitiveRenderer.tsx`'s `PrimitiveNodeRenderer` switch, which explicitly falls through to `return null` for unrecognized `node.type` (graceful degradation is already the established default — supports FR-005 for free).

**Decision**: Add `Chart` as a new top-level entry in `PRIMITIVE_TYPES` (not `PRIMITIVE_SUB_TYPES`, since it's directly emittable, like `Table`), discriminated by `type: "chart"` plus a `chart_type: Literal["line", "bar", "area"]` field (extensible per FR-008/User Story 3 by widening this Literal and adding a `case` arm — additive on both sides). One `render_chart` tool schema per FR-003 branches internally on `chart_type` to validate the right data shape (see data-model.md), rather than accepting one loose generic `data: dict`.

**Rationale**: This is the smallest change that fits the grain of the existing pattern exactly — no new mechanism, no new tool-registration path, no change to how `_ctx.append`/`ContextVar` side-channel or JSON-schema export (`schema.py`) work. `_export_dataclass_schema`'s existing `list[dataclass]` handling (used today by `Table.rows`, `Steps.steps`) covers a chart's `series: list[ChartSeries]` shape without changes to `schema.py`.

**Alternatives considered**:
- **One generic `Chart` primitive with an untyped `data: dict` blob** — rejected: explicitly contradicts FR-003 ("MUST NOT force all chart types through one generic... rendering path") and loses JSON-schema validation of the data shape per chart type.
- **A separate primitive class per chart type (`LineChart`, `BarChart`, `AreaChart`)** — considered viable, rejected in favor of one `Chart` primitive with a `chart_type` discriminator field: keeps `PRIMITIVE_TYPES` from growing one entry per chart type (there could eventually be 17, per Bklit's catalog) and keeps the `PrimitiveNodeRenderer` switch to one `"chart"` case that internally dispatches — matching how a single component library dispatches internally by prop rather than by component identity.

## R5. Data-point volume / rendering performance

**Finding**: No existing Ze UI primitive currently handles more than a few dozen rows (`Table` shows in a `max-h-72 overflow-auto` scroll box; `Steps`/`Connections` are similarly small-N). Bklit charts are Recharts-based, which is SVG-rendered and known to degrade past roughly 500–1,000 plotted points without explicit optimization (data decimation, `isAnimationActive={false}`, memoization).

**Decision**: Cap agent-emittable chart series at a documented soft limit (500 points per series, enforced as a JSON-schema `maxItems` on the `data` array in the chart's LLM-facing schema) rather than building a decimation/virtualization layer now. This keeps scope aligned with the spec's stated assumption ("tens to low hundreds of data points... large-scale/streaming visualization is out of scope").

**Alternatives considered**:
- **Client-side decimation for arbitrarily large series** — deferred: no current use case needs it: goal/workflow/cost data at Ze's single-user scale tops out at daily-granularity series over at most a year (~365 points), well under the cap.

## R6. Testing approach

**Decision**: Python side — unit tests in `core/ze-components/tests/` following the existing pattern (see `tests/test_schema.py`, `tests/test_tools.py`): assert the `render_chart` tool's generated JSON schema shape per `chart_type`, and assert the `Chart` primitive's `export_json_schema()` output. TS side — `packages/ze-ui/src/react/PrimitiveRenderer.test.tsx` gains cases for each starter chart type (renders without throwing, degrades gracefully on an unknown `chart_type`), following the existing test's structure exactly (Vitest + React Testing Library, per `make test-web`).

**Rationale**: Matches constitution Principle V (Test Discipline) and the project's established per-primitive test coverage — no new test tooling needed.
