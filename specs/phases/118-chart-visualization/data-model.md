# Data Model: Chart Visualization

Mirrors the existing primitive pattern (see `core/ze-components/ze_components/organisms/table.py`'s
`Table` dataclass) — a frozen `type` discriminator field plus plain-dataclass fields, exported to
JSON Schema by `ze_components/schema.py` and mirrored 1:1 as a generated TS type consumed by
`packages/ze-ui`.

## Entities

### `ChartPoint` (sub-type — `PRIMITIVE_SUB_TYPES`)

One plotted value.

| Field | Type | Required | Notes |
|---|---|---|---|
| `x` | `str` | yes | Pre-formatted category/axis label (e.g. a date string, a category name). Rendered as inert text (FR-007). |
| `y` | `float` | yes | The plotted value. |
| `series` | `str \| None` | no | Series name this point belongs to, for multi-series charts. Omitted/`None` means the chart's single implicit series. |

### `Chart` (top-level — `PRIMITIVE_TYPES`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `type` | `Literal["chart"]` | yes (frozen, `init=False`) | Discriminator, matches existing pattern. |
| `chart_type` | `Literal["line", "bar", "area"]` | yes | Starter set per FR-001. Widened additively for User Story 3 (e.g. add `"pie"`) — existing values and renderer cases are untouched when a new one is added (FR-008). |
| `data` | `list[ChartPoint]` | yes | `maxItems: 500` in the exported JSON schema (see research.md R5). Empty list is valid input but renders the empty state (FR-006), not an error. |
| `series_labels` | `dict[str, str] \| None` | no | Optional display-name override per series key, for legend text. |
| `x_label` | `str \| None` | no | Axis label. |
| `y_label` | `str \| None` | no | Axis label. |
| `title` | `str \| None` | no | Chart title, rendered above the plot area (mirrors `Table.title`). |
| `legend` | `bool` | no, default `True` | Whether to show the legend — suppressed automatically by the renderer when there's only one series regardless of this flag. |

**Validation rules** (enforced in the `render_chart` tool wrapper in `ze_components/tools.py`, before the `Chart` primitive is constructed — the same layer that today does `_coerce_dict` / list-of-dict coercion for other patterns):

- `chart_type` must be one of the supported `Literal` values; the LLM-facing JSON schema already constrains this at the tool-call level, but the wrapper defends against a stale/malformed call.
- `data` must not exceed the 500-point cap (R5) — truncate with a logged warning rather than reject the whole render, so a partial chart still renders (consistent with FR-006's "sensible" degradation, not a hard failure).
- For `chart_type: "bar"`, points sharing the same `x` are grouped as adjacent bars (grouped-bar behavior), not stacked — stacking is out of scope for the starter set.
- Malformed points (missing `x`/`y`) are dropped individually rather than failing the whole chart, matching FR-006.

### State / lifecycle

`Chart` is a stateless, immutable render primitive — same lifecycle as every other entry in `PRIMITIVE_TYPES` (`Table`, `Steps`, etc.): constructed once per agent turn or page render, appended to the response's primitive tree (via the `ContextVar` side-channel for agent-emitted charts, or directly by developer code for hand-placed charts), and rendered read-only. No chart-specific persistence, no update-in-place, no interactivity state beyond what Recharts/Bklit provides natively (hover tooltip).

## Relationships

- `Chart` composes zero or more `ChartPoint` (via `data`) — same "sub-type used only inside a parent primitive's list field" relationship that `StepItem` has to `Steps` and `ConnectionItem` has to `Connections`.
- `Chart` does not nest other `Primitive` types and is not nested specially by `Col`/`Row` beyond the generic container behavior every primitive already gets.
