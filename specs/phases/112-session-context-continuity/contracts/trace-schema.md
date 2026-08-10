# Contract: `MessageTrace` JSON Shape Extension

Existing endpoint `GET /api/v0/messages/{id}/trace` (Phase 89) returns the `trace`
JSONB column serialized from `MessageTrace`. This feature adds two optional fields;
the endpoint's route signature, `response_model`, and `operation_id` are unchanged —
only the payload shape grows.

## Before (existing fields, unchanged)

```json
{
  "agent": "string",
  "routing_method": "string",
  "confidence": 0.0,
  "score_gap": 0.0,
  "is_compound": false,
  "subtasks": ["..."],
  "memory_chunks": ["..."],
  "tool_calls": ["..."],
  "total_duration_ms": 0
}
```

## After (this feature)

```json
{
  "agent": "string",
  "routing_method": "string",
  "confidence": 0.0,
  "score_gap": 0.0,
  "is_compound": false,
  "subtasks": ["..."],
  "memory_chunks": ["..."],
  "tool_calls": ["..."],
  "total_duration_ms": 0,
  "compaction": {
    "span_start": 0,
    "span_end": 12
  },
  "resume_recap_applied": false
}
```

`compaction` is `null`/omitted when compaction did not run for that turn.
`resume_recap_applied` defaults to `false`. Both are additive — existing consumers of
the trace endpoint (the "Why?" panel, `apps/ze-web`) ignore unknown fields until the
frontend is updated to render them (out of scope for this backend-focused phase; the
Mind/trace panel surfacing these visually is a follow-up UI task, not blocking FR-011
which only requires the data be inspectable via the trace).
