# Research: Trace Telemetry (187b)

## R1. Where to measure stages
- **Decision**: wrap every node at graph build time (`timed(name, fn)`), recording into an in-process per-turn recorder found through a ContextVar.
- **Rationale**: `astream_events` covers only `invoke_raw_turn`; `resume_turn` uses `ainvoke` and emits no events. A wrapper sees every run, including a node that raises `GraphInterrupt` (recorded in `finally`). LangGraph runs nodes in tasks that copy the context, so the ContextVar set before the run reaches them.
- **Alternatives**: `on_chain_start/end` events (resume blind); state reducers (lost for a paused node, need a reset sentinel per turn).

## R2. Surviving a confirmation pause
- **Decision**: a registry keyed by `thread_id` on the container (one running turn per thread); `resume` continues the recorder and counts the gap as `paused_ms`; entries older than 30 minutes are dropped; a resume with no recorder (restart) starts one marked `telemetry_partial`.
- **Rationale**: confirmations wait at most `CONFIRM_TIMEOUT_SECONDS` (900 s); a restart mid-wait is rare and is stated honestly.

## R3. Clocks
- **Decision**: one clock, `time.monotonic()`, for the turn start, stage starts and ends, and `ToolCall.started_at`; wall time only for display.
- **Rationale**: the recorder lives in process, so the monotonic clock is shared across a resume; a wall-clock step can neither reverse nor shift stages, and tool rows and stages agree. (Gauge M-4 replaced a mixed wall/perf design.)

## R4. Model usage
- **Decision**: `CostTracker.record` (already called on every OpenRouter completion with usage) also adds to the current recorder; the main model is the tier's model when set, else the routed agent's model; System One models are recognized by the System One prefix of the price table and summed apart; cost from `estimate_cost_usd`; context fill = largest prompt of the main model over `get_context_window`.
- **Rationale**: one existing choke point; no client change; the same static tables the budget gate uses (clarification Q3: largest prompt).
- **Alternatives**: summing `AgentResult` usage (not carried today); reconciled provider cost (arrives minutes later; stays in Usage).

## R5. Live tool rows
- **Decision**: `ToolCall.call_id` (uuid hex) and `started_at`; `call_tool` hands each returned call to `ctx.tool_sink`, mirroring `token_sink`; the `on_tool_end` partial is deleted.
- **Rationale**: `on_tool_end` reports LangChain tool events with no duration or success; the agent loop's own `ToolCall` holds the truth. Parallel subtasks finish out of order, so ids, not positions, join live and committed rows.

## R6. Judgment bars
- **Decision**: `judgments_from_result` takes `surface` and a per-question bar map built from the surface config in force for the turn; uncalibrated surfaces pass an empty map.
- **Rationale**: the bar is config, read once at decision time; storing it on the row records what decided the turn even after a later recalibration.

## R8. Live frames never block
- **Decision**: a per-turn queue with one sender task, each send bounded by `wait_for(…, 1.0)`, failures dropped and logged.
- **Rationale**: awaiting a WebSocket send in each of about 17 node wrappers would let a slow or displaced client slow the turn (FR-008), and an await in `finally` during a cancel is fragile.

## R9. Parked and approved calls share an id
- **Decision**: a parked call's `call_id` is its `ParkedWrite.call_id`; the approved run reuses `ApprovedCall.call_id`.
- **Rationale**: one call in the committed trace; the live parked row is replaced in place, never shown beside its approved run.

## R7. Rename
- **Decision**: `total_duration_ms` → `tool_duration_ms` everywhere; new `turn_duration_ms` (clarification Q2). Old stored traces keep the old key; the store reader maps a stored `total_duration_ms` to nothing (dropped), since the value was never a total.
- **Rationale**: pre-v1 hard cut; the instrument already labels it "Tool time".
