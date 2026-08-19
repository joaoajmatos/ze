# Quickstart: Validating Chart Visualization

## Prerequisites

- `make install` and `make web-install` already run.
- `make db-up` running (only needed if validating via a live conversation turn, not for the
  unit-test-only checks below).

## 1. Validate the Python side (schema + tool registration)

```bash
make test-components
```

Expected: new tests in `core/ze-components/tests/test_schema.py` /
`tests/test_tools.py` pass, asserting:
- `export_json_schema()` includes a `Chart` def with a `oneOf`/discriminator entry for
  `"chart"`, matching `contracts/chart-primitive.md` §2.
- `render_chart`'s registered `ToolSpec.schema` matches `contracts/chart-primitive.md` §1
  (three `chart_type` enum values, `data` with `maxItems: 500`).
- Malformed points (missing `x`/`y`) are dropped, not raised, per data-model.md's validation
  rules.

## 2. Validate the TS side (renderer)

```bash
make test-web
```

Expected: `packages/ze-ui/src/react/PrimitiveRenderer.test.tsx` gains passing cases for:
- A `chart_type: "line"`, `"bar"`, and `"area"` node each render without throwing.
- An unrecognized `chart_type` renders nothing (no crash), matching the file's existing
  fallback behavior for unknown primitives.

## 3. Validate end-to-end via a live conversation (User Story 1)

1. `make dev-full`
2. In the web client, send a message that plausibly makes an agent reach for a chart, e.g.
   "show me how my costs have trended over the last 2 weeks" (routes to an agent with cost
   data available).
3. Confirm: a rendered line or area chart appears inline in the chat, legible in both light
   and dark theme (toggle via the app's theme control), with the series colored from the
   `--chart-1`…`--chart-5` tokens added in `globals.css` (research.md R3) — not default
   Recharts colors.

## 4. Validate direct placement on a dashboard page (User Story 2)

1. Pick an existing dashboard-style page (e.g. `apps/ze-web/src/pages/.../CostsPage.tsx` or
   similar) and add one of the starter chart components from
   `apps/ze-web/src/shared/ui/charts/` directly, with a small static dataset.
2. `make web`, navigate to the page.
3. Confirm: the chart renders styled identically to the same chart type rendered via the
   agent path in step 3 above (same colors, same chrome) — no separate theming needed.

## 5. Validate graceful degradation (Edge Cases)

- Manually construct a `Chart` primitive with `chart_type: "pie"` (unsupported in the
  starter set) and confirm the surrounding response still renders, with the chart itself
  omitted — not a broken page.
- Construct one with `data: []` and confirm an empty-state message renders instead of a
  blank/broken chart area.

## 6. Validate extensibility (User Story 3)

- Follow the pattern used for the starter set to add one additional chart type (e.g.
  `"pie"`): widen the `chart_type` Literal in `data-model.md`'s `Chart` entity, add the
  corresponding Bklit component via the shadcn CLI, add one `case` branch to the TS
  dispatch. Re-run steps 1 and 2 above — all existing chart-type tests must still pass
  unchanged (SC-004).
