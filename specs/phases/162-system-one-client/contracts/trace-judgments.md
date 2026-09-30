# Contract: MessageTrace judgments

**Feature**: `162-system-one-client`  
**Verbatim**: `MessageTrace`, `judgments`, `consumed`

## Domain

`JudgmentTrace` on `MessageTrace.judgments` (see [data-model.md](../data-model.md)). `record_trace` copies `AgentState["judgments"]`. No new graph node.

## REST

`GET /api/v0/messages/{id}/trace` and batch traces: `MessageTraceResponse.judgments` default `[]`.

Each item:

| Field | JSON |
|---|---|
| `question_id` | string |
| `kind` | `noul` \| `choice` \| `score` |
| `answer` | string, number, or null |
| `probabilities` | object or null |
| `peakedness` | number or null |
| `model` | string or null |
| `input_tokens` | int or null |
| `latency_ms` | int |
| `consumed` | bool |
| `skip_reason` | string or null |

OpenAPI must declare the field so `make codegen` updates `@ze/client`. Additive: missing key on old traces → `[]`.

## WebSocket

`WsTraceUpdateFrame.judgments` same shape, default `[]`. `toTraceFrame` copies it. Partial `trace_update` frames may omit it (client treats missing as empty).

## UI

`widgets/trace-panel` `JudgmentsSection`: hide when `judgments` is empty or missing. When present, show question id, kind, answer or skip reason, `consumed` vs unused, reported model. Do not invent confidence for noul.

## Tests

- Schema: `judgments` on `MessageTraceResponse` and `WsTraceUpdateFrame`.
- Construct a trace with two judgments, exactly one `consumed=true`.
- Skip row: `skip_reason` set, `answer` null, not a fake high noul.
