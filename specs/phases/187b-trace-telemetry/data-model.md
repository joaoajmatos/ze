# Data Model: Trace Telemetry (187b)

JSON on `messages.trace` (no migration). New and changed fields on `MessageTrace`:

| Field | Type | Notes |
|---|---|---|
| tool_duration_ms | int | renamed from `total_duration_ms` (sum of tool durations) |
| turn_duration_ms | int \| null | wall time from turn start to the stamp; null on traces before 187b |
| paused_ms | int | time waiting for confirmations (0 when none) |
| stages | list[StageTiming] | order of completion |
| usage | TurnUsage \| null | |
| routing_scores | list[RoutingScore] | top 9 by score; empty when routing used no embedding scores |
| routing_thresholds | {threshold: float, gap: float} \| null | |
| telemetry_partial | bool | true when a resume found no recorder (restart) |

**StageTiming**: `name` (graph node name), `start_ms` (offset from turn start), `duration_ms`, `run` (1, then 2… after each resume).

**TurnUsage**: `main_model`, `models: list[ModelUsage]`, `context_fill` (0–1+, may exceed 1 if the provider truncated), `context_window`, `estimated`, `system_one_tokens`.

**ModelUsage**: `model`, `calls`, `prompt_tokens`, `completion_tokens`, `max_prompt_tokens`, `cost_usd`, `estimated`.

**RoutingScore**: `agent`, `score`.

**ToolCallTrace** additions: `call_id` (str), `start_offset_ms` (int \| null).

**JudgmentTrace** additions: `surface` (str \| null), `bar` ({name: str, value: float} \| null).

**ze-agents `ToolCall`** additions: `call_id`, `started_at` (wall seconds). **`AgentContext.tool_sink`**: runtime-only callable.

**RoutingEnvelope** additions: `threshold`, `gap_threshold`.

**TurnTelemetry** (in process, never stored): turn wall start, stages, per-model accumulators, run, paused_ms, partial flag, emit.
