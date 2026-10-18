# Contract: trace telemetry fields

## Partial `trace_update` frames (WS, `partial: true`)
One frame per finished node:
```json
{ "type": "trace_update", "message_id": "…", "partial": true,
  "stages": [{ "name": "fetch_context", "start_ms": 212, "duration_ms": 88, "run": 1 }] }
```
Routing partial (embed_route) adds:
```json
"routing_scores": [{ "agent": "calendar", "score": 0.83 }, { "agent": "companion", "score": 0.71 }],
"routing_thresholds": { "threshold": 0.78, "gap": 0.05 }
```
Memory partial adds `extraction_confidence` per fact chunk (null for episodes and profile).
Tool partial (one per finished call, from the tool sink):
```json
"tool_calls": [{ "call_id": "9f…", "name": "list_events", "agent": "calendar",
                 "start_offset_ms": 640, "duration_ms": 312, "success": true, "result_snippet": "…" }]
```
Clients append `stages` and merge `tool_calls` by `call_id`.

## Committed trace (final `trace_update` frame and `GET /api/v0/messages/{id}/trace`)
```json
{ "tool_duration_ms": 312, "turn_duration_ms": 2140, "paused_ms": 0,
  "stages": [ … every stage of every run … ],
  "usage": { "main_model": "anthropic/claude-sonnet-4-6",
             "models": [{ "model": "anthropic/claude-sonnet-4-6", "calls": 2, "prompt_tokens": 9120,
                          "completion_tokens": 410, "max_prompt_tokens": 5200, "cost_usd": 0.0335, "estimated": false }],
             "context_fill": 0.026, "context_window": 200000, "estimated": false, "system_one_tokens": 1840 },
  "routing_scores": [ … ], "routing_thresholds": { … },
  "telemetry_partial": false,
  "tool_calls": [{ "call_id": "9f…", "start_offset_ms": 640, "call_index": 0, … }],
  "judgments": [{ "question_id": "route", "surface": "routing", "bar": { "name": "choice_trust", "value": 0.5 }, … }] }
```
Removed: `total_duration_ms`. Every new field is optional on read (traces before 187b lack them).
