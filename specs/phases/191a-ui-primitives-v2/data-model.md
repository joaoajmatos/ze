# Data Model: UI Primitives v2 (191a)

Descriptors only; no storage.

## PrimitiveAction (discriminated by `kind`)

| kind | Fields | Handled by |
|---|---|---|
| ask | text (1–500 chars) | browser: `sendTurn` on the selected thread |
| tool | owner (agent name), tool (a WRITE tool with `ui_action=True`), args (scalar values matching the tool's schema; `"{key}"` placeholder allowed in row actions) | server: `ui_action` → `run_action` through `call_tool` |
| navigate | route (starts with `/`, a place route, optional `#section`) | browser: router |
| compose | compose (`slipping` \| `decisions` \| …, 184), topic? | browser: `sendTurn` with preset context |

## New primitives

| type | Fields |
|---|---|
| entity_facet | title, facts: [{text, claim, source?, at?}], more?: PrimitiveAction |
| stat_row | items: [{label, value, delta?, direction?: up\|down\|flat}] (1–6) |
| claim_list | title?, items: [{text, claim, action?: PrimitiveAction}] |
| sparkline | label, value?, points: number[] (≤ 60) |
| card | title, body?, children: Primitive[], actions: Button[], claim? |
| table (extended) | + keys?: string[] (one per row), row_actions?: [{label, action}] |

## Fallback node (client only)

`{ type: "__fallback", originalType, fields: [[name, value]] (≤ 12 scalars), children: Primitive[] }`.

## Transport

`ui_version: "2.0"` on the WS `message` frame, `PluginPageResponse` and composed-answer payloads for newly built trees. Absent (stored trees) or `1.x` → legacy rendering.

## UiActionGate (server, in process)

request_id, thread_id, agent, tool, args, parked (ParkedWrite with a real `call_id`), timer task. Popped on confirm, timeout or supersede; replayed on reconnect; lost on restart (a later `confirm` gets "That request expired.").
