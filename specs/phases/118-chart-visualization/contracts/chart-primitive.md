# Contract: `chart` Primitive

Two interfaces are affected, both generated from the Python dataclasses in `data-model.md` —
no interface is hand-written twice.

## 1. LLM-facing tool contract (`render_chart`)

Registered in `core/ze-components/ze_components/tools.py` via the existing `render_tool`
decorator, exactly like `render_metric`/`render_table`. The JSON schema below is what
`build_render_schema()` derives from the private `_ChartSchema` dataclass and is what the
LLM sees as the tool's input schema — this is the contract an agent actually calls against.

```json
{
  "type": "object",
  "properties": {
    "chart_type": { "enum": ["line", "bar", "area"] },
    "data": {
      "type": "array",
      "maxItems": 500,
      "items": {
        "type": "object",
        "properties": {
          "x": { "type": "string" },
          "y": { "type": "number" },
          "series": { "type": "string" }
        },
        "required": ["x", "y"],
        "additionalProperties": false
      }
    },
    "series_labels": { "type": "object" },
    "x_label": { "type": "string" },
    "y_label": { "type": "string" },
    "title": { "type": "string" },
    "legend": { "type": "boolean" }
  },
  "required": ["chart_type", "data"],
  "additionalProperties": false
}
```

**Tool description** (surfaced to the LLM, following the existing tools' style — see
`render_table`'s and `render_metric`'s docstrings): "Render a chart. Use for trends over time
(`chart_type: line` or `area`) or category comparisons (`chart_type: bar`). Each data point:
`{x (pre-formatted label, required), y (numeric value, required), series (optional, for
multi-series charts)}`. Prefer `render_table` for exact tabular values the user needs to read
precisely; use a chart when the shape of the data (trend, comparison) is the point."

## 2. Export/render contract (`Chart` primitive)

Part of the shared `Primitive` discriminated union exported by `export_json_schema()` in
`ze_components/schema.py`, consumed by `packages/ze-ui`'s codegen
(`generated/types.gen.ts`, `generated/schema.json`) exactly like every other entry in
`PRIMITIVE_TYPES`. No hand-maintained duplicate of this shape is to exist on the TS side —
it is generated, matching every other primitive today.

```json
{
  "Chart": {
    "type": "object",
    "properties": {
      "type": { "const": "chart" },
      "chart_type": { "enum": ["line", "bar", "area"] },
      "data": { "type": "array", "items": { "$ref": "#/$defs/ChartPoint" } },
      "series_labels": { "type": "object" },
      "x_label": { "type": "string" },
      "y_label": { "type": "string" },
      "title": { "type": "string" },
      "legend": { "type": "boolean" }
    },
    "required": ["type", "chart_type", "data"],
    "additionalProperties": false
  },
  "ChartPoint": {
    "type": "object",
    "properties": {
      "x": { "type": "string" },
      "y": { "type": "number" },
      "series": { "type": "string" }
    },
    "required": ["x", "y"],
    "additionalProperties": false
  }
}
```

**Renderer contract**: `PrimitiveNodeRenderer`'s switch in
`packages/ze-ui/src/react/PrimitiveRenderer.tsx` gains a `case "chart":` arm dispatching to a
`ChartRenderer` that itself switches on `node.chart_type` to pick the corresponding Bklit
component (`LineChart`/`BarChart`/`AreaChart`). An unrecognized `chart_type` value (e.g. from
a newer backend the client hasn't caught up to) follows the file's existing default behavior
for the outer switch — render nothing rather than throw (FR-005).

## 3. Direct-placement contract (developer-authored pages)

The same `apps/ze-web/src/shared/ui/charts/` components installed for the SDUI path are
exported for direct import — no separate "developer" chart API. A dashboard page imports
e.g. `LineChart` from `shared/ui/charts` and passes props matching the same `ChartPoint`
shape used above, so the two usage paths (User Story 1 and User Story 2) are guaranteed to
render identically by construction (per research.md R4's rationale), not by convention.
