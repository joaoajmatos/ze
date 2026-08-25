# Data Model: Memory Graph Charts

No new persisted entities. Two derived view-models, both computed from data already fetched.

## `FactDigestItem` (backend schema change)

`apps/ze-api/ze_api/api/schemas.py` — add one field:

| Field | Type | Change |
|---|---|---|
| `created_at` | `datetime` | **new** — populated from `MemoryFact.created_at` in the entity-detail service path |

## `EntityActivityPoint` (frontend, derived — not a new API type)

Computed client-side in `EntityDetailPanel` (or a small `lib/` helper alongside it) from `detail.facts` + `detail.episodes`:

| Field | Type | Source |
|---|---|---|
| `x` | `string` | Bucketed date (e.g. day) from `created_at` |
| `y` | `number` | Count of facts + episodes created_at that bucket |
| `series` | `"fact" \| "episode"` | Which digest list the item came from — lets the chart optionally split by kind |

Maps directly onto the existing `ChartPoint` shape from spec 118 — no new frontend type needed, just a mapping function `entityActivitySeries(detail: EntityDetailResponse): ChartPoint[]`.

## `GraphComposition` (frontend, derived — not a new API type)

Computed client-side in the graph widget from the currently-loaded React Flow node/edge state:

| Field | Type | Source |
|---|---|---|
| `x` | `string` | `entity_type` (or `predicate` for the relation-type variant) |
| `y` | `number` | Count of nodes (or edges) with that type |

Same `ChartPoint` shape, produced by a `graphComposition(nodes: GraphEntityNode[]): ChartPoint[]` helper (and an edge-type variant), recomputed on every node-list change (React `useMemo` keyed on the node/edge arrays).

## Relationships

- `EntityActivityPoint` and `GraphComposition` are both transient, render-only view-models — recomputed on every relevant data change, never persisted, never sent back to the server.
