# Implementation Plan: Trace Telemetry (187b)

**Branch**: `187b-trace-telemetry` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md with the 2026-10-18 clarifications (user: all recommended); `main` at 29f7f307 (187 landed; line numbers below are on it); Canvas's readout of the degraded instruments (floor Handoffs note).

## Summary

One per-turn recorder, `TurnTelemetry`, measures the turn on the server and stamps the result onto the reply's `MessageTrace` before anyone saves or sends it.

- **Stages.** Every graph node is wrapped at build time. The wrapper records the node's start offset and duration on the recorder, including when the node pauses for a confirmation, and sends a partial frame with that one stage.
- **Totals and usage.** `CostTracker.record` also adds each model call to the recorder (tokens per model, largest prompt). When the turn ends, the recorder stamps `stages`, `turn_duration_ms`, `paused_ms`, `tool_duration_ms` (renamed from `total_duration_ms`) and `usage` onto the trace.
- **Routing and judgments.** The router puts its thresholds and sorted scores on the envelope. `judgments_from_result` takes the surface name and each question's bar.
- **Tools and memory.** `ToolCall` gains `call_id` and `started_at`. `call_tool` hands every finished call to `ctx.tool_sink`, which ze-core forwards as a truthful live row. Delegated calls get the sink too, and their id and start survive the nested-call round trip. The live memory frame gains `extraction_confidence`.
- **Web.** 187's instruments read these fields. The client's arrival-time stamps and the "Tool time" stand-in are deleted.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 5, React 19, Zustand.
**Primary Dependencies**: none new (LangGraph, the existing OpenRouter client, the static price and context-window tables).
**Storage**: none new. The trace is JSON on `messages.trace`; old traces lack the new fields.
**Testing**: pytest with fake graphs, a fake monotonic clock (patched through the recorder's clock function) and mocked interfaces; vitest for the instruments with fixture traces.
**Target Platform**: Linux container + browser.
**Project Type**: web service + web app.
**Constraints**: telemetry never fails or delays a turn (every recorder call is guarded); ze-agents never imports ze-core (the tool sink is a plain callable on `AgentContext`); plugins untouched.
**Scale/Scope**: about 17 nodes per turn; one recorder per running turn (one turn per thread at a time).

## Constitution Check

| Principle | Check |
|---|---|
| I Spec-first | spec, clarifications, plan, research, data model, contract, quickstart, tasks. |
| III Layered packages | Recorder and node wrapper in ze-core; `ToolCall.call_id`/`started_at` and `AgentContext.tool_sink` in ze-agents (no ze-core import); schemas in ze-api; instruments in ze-web. |
| IV Typed Python | Dataclasses `StageTiming`, `ModelUsage`, `TurnUsage`, `RoutingScore`, `JudgmentBar`; no Pydantic outside ze-api schemas. |
| V Tests | Fail-first per task; fake clocks. |
| VIII Hard cuts | `total_duration_ms` renamed `tool_duration_ms` everywhere (types, store reader, REST, WS, seed loader, web); the `on_tool_end` partial branch in `turn.py` deleted (replaced by the tool sink); the web arrival stamps (`pendingArrivals`, `arrivalsByMessage`, `pendingSentAt`, `sentAtByMessage`) deleted. |

Gate: pass.

## Blast radius

`graphify affected` is re-run in T001; from grep on `main` 7ca568ba:

| Symbol | Callers | Change |
|---|---|---|
| `MessageTrace` (`ze_core/conversation/messages/types.py`) | `record_trace` (`nodes/trace.py`), `write_memory` (`nodes/memory.py:155`), `messages/store.py:311` (reader), `api/v0/messages/{schemas,router}.py`, `api/ws/schemas.py`, `interface/native.py`, `ze_seed/narrative/loader.py:124` and `ze_seed/narrative/persona.yaml:1375,1400,1421,1439` (the YAML keys), tests (`test_state_serde.py`, `test_message_store.py`, `test_schemas_rollback.py`, `test_messages_route.py`, `test_judgments_trace_schema.py`, `test_sources_trace_schema.py`) | `total_duration_ms` → `tool_duration_ms`; adds `turn_duration_ms`, `paused_ms`, `stages`, `usage`, `routing_scores`, `routing_thresholds`, `telemetry_partial`. |
| `ToolCallTrace` | `_extract_tool_calls` (`nodes/trace.py`), store reader, schemas | Adds `call_id`, `start_offset_ms`. |
| `JudgmentTrace`, `judgments_from_result` (`messages/judgments.py`) | `nodes/routing.py`, `nodes/skills.py`, `nodes/tier.py`, `nodes/memory.py` (`_outcome_row` too) | Adds `surface`, `bar`; the four callers pass their surface and bar map. |
| `RoutingEnvelope` (`routing/types.py`) | router (`routing/router.py`), `embed_route`, `turn.py` partial | Adds `threshold`, `gap_threshold`; partial frame gains `routing_scores` (top scores) and `routing_thresholds`. |
| `ToolCall` (`ze_agents/types.py`), `BaseAgent.call_tool` (`base_agent.py:355-540`) | every agent loop; `_extract_tool_calls` | Adds `call_id` and `started_at` (monotonic); `call_tool` emits each returned call to `ctx.tool_sink`. |
| `delegate_to_agent` (`ze_agents/delegate.py:267` builds `sub_ctx` field by field; `:318-330` serializes nested calls with a fixed field list) | conductor turns | `sub_ctx` gets `tool_sink=ctx.tool_sink` (and `token_sink` stays as it is today); the nested dict carries `call_id` and `started_at`. |
| `flatten_tool_calls` (`ze_agents/nested_tools.py:38-57`) | `record_trace`, retry eligibility | Restores `call_id` and `started_at` from nested dicts (no new uuid). |
| `ParkedWrite.call_id`, `ApprovedCall.call_id` (`ze_agents/park.py:46,60`) | park and resume | A parked call's `ToolCall.call_id` is its `ParkedWrite.call_id`; the approved call run on resume reuses `ApprovedCall.call_id`, so live and committed show one call. T001 confirms how `ParkedWrite.call_id` is derived. |
| `AgentContext.token_sink` pattern (`ze_agents/types.py:113-115`) and its wiring (`nodes/execution.py:299,323,400,474`) | execute_tool, subtasks, delegates | Mirror: `tool_sink` beside `token_sink`. |
| `CostTracker.record` (`telemetry/tracker.py`) | OpenRouter client, System One client | Also adds the call to the current `TurnTelemetry`. |
| `invoke_raw_turn`, `resume_turn` (`conversation/turn.py`) | `wiring/container.py:165`, `api/ws/{turns,confirmation,rollback_state}.py` | Start or continue the recorder; stamp `final_state["message_trace"]`; delete the `on_tool_end` branch; add `extraction_confidence` to the memory partial. |
| Graph builder (`orchestration/graph.py:72-97,170`) and the workflow graph | — | Every `add_node` goes through `timed(name, fn)`. |
| `send_trace_partial` (`interface/native.py:146-169`) | `turn.py` | Base frame: `total_duration_ms` → `tool_duration_ms`; stage, usage and tool fields pass through. |
| Web rename sites (`make codegen` renames the field, so these change with the contract step): `features/trace-state/lib/toTraceFrame.ts:20` and `.test.ts:16,68,90`, `useTraceStore.test.ts:22`, `ui/trace/rows/ConductorRow.test.tsx:21`, `instruments/fixtures.ts:31`, `tools.test.ts:21`, `readouts.ts:31`; `entities/message-trace/ui/MessageTracePanel.tsx:41` | history path (`useSessionTraces.ts:28` → `toTraceFrame`), instruments | Renamed by lead in T003. `MessageTracePanel` has no importer since 187 (only the entity index re-exports it): deleted with its export. `toTraceFrame` copies a fixed field list, so lane `web` adds the new fields in T012. |
| Web: `useTraceStore` (`features/trace-state/model/useTraceStore.ts`), `widgets/assemble/lib/instruments/{signal,readouts,routing,judgments,tools,memory}.ts` and `ui/trace/{SignalPath,Readouts,RoutingInstrument,JudgmentGauges,ToolsTimeline,MemoryConstellation}.tsx` | Ask trace panel | Read the new fields; merge partial `stages` and tool rows by `call_id`; arrival stamps deleted. |

## Design

### ze-core: `telemetry/turn.py` (new)

- `StageTiming(name: str, start_ms: int, duration_ms: int, run: int)`; `ModelUsage(model, calls, prompt_tokens, completion_tokens, max_prompt_tokens, cost_usd, estimated: bool)`; `TurnUsage(main_model: str | None, models: list[ModelUsage], context_fill: float | None, context_window: int | None, estimated: bool, system_one_tokens: int)`.
- `TurnTelemetry`: `started` (`time.monotonic()`; `started_wall` from `time.time()` for display only), a list of stages, per-model accumulators, `run` (1, +1 on each resume), `paused_ms`, `partial` (True when it was created by a resume because none existed), an optional async `emit(fields)`.
  - `record_stage(name, started, ended)`: both from `time.monotonic()`; `start_ms = started - turn start`, `duration_ms = ended - started`. One clock for stages and tool rows (`ToolCall.started_at` is monotonic too), valid across a resume because the registry is in process.
  - `pause()` stamps `paused_at` when a run returns interrupted; `resume` adds `now - paused_at` to `paused_ms`.
  - `freeze()`, called by `stamp`: records that arrive later (fire-and-forget tasks that copied the ContextVar) are ignored. Work that finishes before the stamp counts; the stamp is the line.
  - Sending: `emit(fields)` puts the frame on a per-turn queue and returns at once; one worker task sends in order with `asyncio.wait_for(send, 1.0)` and drops a frame that fails or times out (logged). `finish` stops the worker. A slow or displaced client never delays a node.
  - The send target (run 1's `pending_message_id` and thread) is set once by `invoke_raw_turn` and kept for later runs; a recorder recreated after a restart has none (no live stage frames, stored trace stamped partial).
  - `record_call(model, prompt_tokens, completion_tokens, audio_seconds=None)`: rows with `audio_seconds` (transcription) are skipped.
  - `stamp(trace, main_model) -> MessageTrace`: returns `replace(trace, stages=…, turn_duration_ms=now - start, paused_ms=…, usage=…, telemetry_partial=…)`. Usage: cost from `estimate_cost_usd`; `estimated` when a model fell back to `DEFAULT_PRICING` or `DEFAULT_CONTEXT_WINDOW_TOKENS`; `context_fill = max_prompt_tokens(main) / get_context_window(main)`; models whose slug starts with a System One prefix (`typesafe/jev-`, read from the price table's System One entry) are summed into `system_one_tokens` and kept out of `main_model`.
- `TurnTelemetryRegistry` on the `Container`: `start(thread_id)` (replaces any entry for the thread), `resume(thread_id)` (returns the existing one, adds the paused gap, `run += 1`; creates a `partial` one if none), `finish(thread_id)`; entries older than 30 minutes are dropped on each `start`. `finish` is also called on the paths that end a paused turn without a stamped reply: the confirmation timeout (`api/ws/confirmation.py:292-321`) when it finds nothing to resume, a superseded gate, and a cancelled turn (T001 lists the exact sites).
- `current_turn_telemetry` ContextVar, set by `invoke_raw_turn`/`resume_turn` for the run. Every method is wrapped so an exception is logged (`turn_telemetry_failed`) and swallowed.

### ze-core: node wrapper (`orchestration/timing.py`, new)

- `timed(name, fn)` returns an async node with the signature `(state, config: RunnableConfig)` (LangGraph injects `config` by parameter name), calls `fn` with the same arguments, awaiting it when it returns an awaitable (overrides may be sync functions or partials), notes `time.monotonic()` before and after, and in `finally` records the stage and calls the non-blocking `emit({"stages": [...]})`. A node that raises `GraphInterrupt` still records its run, and LangGraph re-runs an interrupted node from its start on resume (`execution.py:128,154`), so `await_write_confirmation` appears once per run.
- `graph.py` applies `timed` to every `add_node`, including overrides and the plugin `pre_route_node`. The workflow graph builder does the same. With no recorder (eval harness, unit graphs), the wrapper calls `fn` and nothing else.
- Main model: the stamp reads `state["tier"].model` when set, else the routed agent's resolved model from `agent_context`; compound turns use the synthesize model.

### ze-core: `turn.py`

- `invoke_raw_turn`: `registry.start(thread_id)`, set the ContextVar, `emit = lambda f: interface.send_trace_partial(pending_message_id, f, thread_id)`. On graph end without an interrupt: `final_state["message_trace"] = telemetry.stamp(trace, main_model)` and `registry.finish`. On interrupt: keep the recorder. On error: stamp what was reached when a trace exists.
- `resume_turn`: `registry.resume(thread_id)`, same ContextVar and stamp.
- The embed_route partial adds `routing_scores` (top `ROUTING_SCORES_SHOWN = 9` by score, matching `shortlist_k`) and `routing_thresholds {threshold, gap}`; the fetch_context partial adds `extraction_confidence`.
- The `on_tool_end` branch is deleted.
- `tool_sink`: built in `invoke_raw_turn` (and resume) and put in `config["configurable"]["tool_sink"]`. It maps a `ToolCall` to a live row `{call_id, name, agent, gate, start_offset_ms, duration_ms, success, result_snippet}` and emits `{"tool_calls": [row]}`. A parked row has `gate: "parked"` and reads as waiting; its approved run arrives later with the same `call_id` and replaces it. `execute_tool` passes the sink into `AgentContext.tool_sink` beside `token_sink` (`execution.py:299,323,400,474`), and `delegate_to_agent` copies it into `sub_ctx`.

### ze-core: trace building

- `record_trace`: `tool_duration_ms = sum(durations)` (renamed), `routing_scores`/`routing_thresholds` from the envelope, tool rows carry `call_id` and `start_offset_ms` (from `ToolCall.started_at` against the recorder's start, or null without a recorder).
- `judgments_from_result(result, *, question_kinds, consumed, skip_reason=None, surface: str, bars: Mapping[str, JudgmentBar | None])`. Each row gets `surface` and `bars.get(qid)`; a surface with null bars passes `{}`, and rows say `bar: null` with `surface` set (the instrument reads that as uncalibrated). Bar maps, read from the surface config in force:
  - routing: the Choice question → `choice_trust`, the multi-specialist Noul → `multi_specialist_hold`;
  - skills: Choice → `choice_trust`, `needs_skill` → `needs_skill_hold`;
  - complexity/tier: `needs_deep_reasoning` → `simple_max`;
  - commitment intake: Choice → `choice_hold`, family → `family_hold`, biography → `biography_hold`, `is_open_concern` → `loop_hold`, `explicit_declaration` → `explicit_hold`, `resolves_existing` → `resolves_hold`; `_outcome_row` gets `surface="commitment_intake"` and no bar.
  
  T001 confirms the question ids against each judge module.

### ze-core: router

- `RoutingEnvelope` gains `threshold: float` and `gap_threshold: float`, set from `RouterConfig` on every envelope the router builds (forced, screen, preset and open-query envelopes set them too, so the instrument always has the bars; their `raw_scores` stay as today).

### ze-agents

- `ToolCall.call_id: str = field(default_factory=lambda: uuid4().hex)`, `ToolCall.started_at: float | None = None` (the same `time.monotonic()` value `call_tool` already takes as `start`).
- `AgentContext.tool_sink: Any | None = field(default=None, repr=False)`.
- `call_tool` funnels every return through `_finish(ctx, tool_call)`, which calls `ctx.tool_sink(tool_call)` inside try/except (the sink only enqueues; an error is logged, never raised). A parked call sets `call_id` from its `ParkedWrite`; a call run under `ApprovedCall` sets it from `ApprovedCall.call_id`.
- `delegate_to_agent`: `sub_ctx` gains `tool_sink=ctx.tool_sink`; the nested dict adds `call_id` and `started_at`. `flatten_tool_calls` restores both.

### ze-api

- `ToolCallTraceResponse` gains `call_id`, `start_offset_ms`; `JudgmentTraceResponse` gains `surface`, `bar`; `MessageTraceResponse` and `WsTraceUpdateFrame` rename `total_duration_ms` → `tool_duration_ms` and add `turn_duration_ms`, `paused_ms`, `stages`, `usage`, `routing_scores`, `routing_thresholds`, `telemetry_partial`, all optional; `router.py:121` and `native.py:162` follow. `make codegen`.

### ze-web (lane `web`)

- `toTraceFrame` (`features/trace-state/lib/`): passes every new field from the REST trace to the frame, so a reply opened from history shows the same instruments as live.
- `useTraceStore`: delete `pendingArrivals`, `arrivalsByMessage`, `pendingSentAt`, `sentAtByMessage` and `stagesIn`; `mergePartialTrace` appends `stages` and merges `tool_calls` by `call_id` (a later row for the same id replaces the earlier one).
- `signal.ts`: `stagesFor(trace, streaming)` maps server stages (in order) to the signal path's labels (`preprocess`, `screen`, `route`, `decompose`, `memory`, `skills`, `tier`, `preflight`, `execute`, `confirm`, `correlate`, `surface`, `synthesize`, `trace`, `memory write`); offsets come from `start_ms`. Stages from a second run are drawn after a gap marked with `paused_ms`.
- `readouts.ts`: the total is `turn_duration_ms` (with "partial" when `telemetry_partial`), active time is total minus `paused_ms`, tool time is `tool_duration_ms`; the context-fill bar is clamped at 100% while the number shows the real value; tokens, cost and context fill from `usage` ("est." when `estimated`); System One tokens apart.
- `routing.ts`: the shortlist bars from `routing_scores` against `routing_thresholds`.
- `judgments.ts`: each gauge draws its `bar`; null with a surface reads "uncalibrated".
- `tools.ts`: rows keyed by `call_id`, placed by `start_offset_ms`; a `gate: "parked"` row reads "waiting for you", not failed.
- `memory.ts`: live chunks show `extraction_confidence`.
- A trace without the new fields (recorded before this phase) keeps today's fallback text, with no arrival stamps.

## Project Structure

### Documentation (this feature)

```text
specs/phases/187b-trace-telemetry/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md, tasks.md
├── contracts/trace-telemetry.md
└── checklists/{requirements,telemetry}.md
```

### Source Code

```text
core/engine/ze-core/ze_core/telemetry/{turn.py (new),tracker.py,__init__.py}
core/engine/ze-core/ze_core/orchestration/{timing.py (new),graph.py,nodes/{trace,routing,skills,tier,memory,execution}.py}
core/engine/ze-core/ze_core/conversation/{turn.py,messages/{types,judgments,store}.py}
core/engine/ze-core/ze_core/routing/{types,router}.py ; ze_core/container.py (registry)
core/contracts/ze-agents/ze_agents/{types.py,base_agent.py,delegate.py,nested_tools.py}
core/ops/ze-seed/ze_seed/narrative/{loader.py,persona.yaml}
apps/ze-api/ze_api/api/ws/confirmation.py (finish on timeout and superseded paths)
apps/ze-api/ze_api/api/v0/messages/{schemas,router}.py ; api/ws/schemas.py ; interface/native.py
packages/ze-client/src/generated/*
apps/ze-web/src/features/trace-state/{lib,model}/* ; apps/ze-web/src/widgets/assemble/{lib/instruments,ui/trace}/* ; apps/ze-web/src/entities/message-trace/ (MessageTracePanel deleted)
```

## Docs touched

- `docs/native-interface.md`: the `trace_update` frame's new fields and the per-stage partials; the rename.
- `docs/architecture.md`: the trace section (stages, totals, usage, the recorder) and the graph flow note that every node is timed.
- `docs/frontend.md`: the trace instruments read server stages; the arrival-stamp wording is removed.
- `AGENTS.md` repo-layout block: `telemetry/` line names `turn.py` (TurnTelemetry); `orchestration/` line names `timing.py`.
- `AGENTS.md`: phase row 187b; `specs/README.md` row 187b.

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first; T002–T004):
- **Types:** the dataclasses and the `MessageTrace`/`ToolCallTrace`/`JudgmentTrace`/`RoutingEnvelope`/`ToolCall`/`AgentContext` field changes, including the `tool_duration_ms` rename across every reader and test, the seed YAML keys, and the web rename sites (so `make typecheck-web` stays green from the codegen on); `MessageTracePanel` deleted.
- **Signatures:** the `judgments_from_result` signature with `surface`/`bars` and its four callers passing `surface` with empty bar maps.
- **API:** the ze-api schemas and `make codegen`.
- **Recorder:** `TurnTelemetryRegistry` on the container and the `current_turn_telemetry` ContextVar, as no-op stubs with final signatures.

| Lane | Model / role | Owns (disjoint) | Tasks | Starts after | Reviewer |
|---|---|---|---|---|---|
| lead | Sonnet ENG lead | `messages/{types,store}.py`, `messages/judgments.py`, `routing/types.py`, `ze_agents/types.py`, `api/v0/messages/*`, `api/ws/schemas.py`, `interface/native.py`, `ze_seed/narrative/{loader.py,persona.yaml}`, `packages/ze-client/src/generated/*`, `ze_core/container.py`, the Python and web files the rename touches, `entities/message-trace/*`; merges, gates | T001–T004, T014, T015 | - | Gauge |
| recorder | Sonnet ENG | `telemetry/{turn,tracker,__init__}.py`, `orchestration/{timing,graph}.py`, the workflow graph builder, `conversation/turn.py`, `api/ws/confirmation.py` (finish calls), and their tests | T005–T007, T007a | contract step | floor Reviewer |
| tools | Sonnet ENG | `ze_agents/{base_agent,delegate,nested_tools}.py`, `nodes/execution.py`, `nodes/trace.py`, and their tests | T008–T009 | contract step | floor Reviewer |
| bars | Sonnet ENG | `routing/router.py`, `nodes/{routing,skills,tier,memory}.py`, and their tests | T010–T011 | contract step | floor Reviewer |
| web | Sonnet ENG | `features/trace-state/{lib,model}/*`, `widgets/assemble/lib/instruments/*`, `widgets/assemble/ui/trace/*`, and their tests | T012–T013 | contract step (codegen types) | floor Reviewer |
| docs | Haiku DOCS | the files in "Docs touched" | T016–T018 | T015 | floor Reviewer |

**Rules**: one lane per file at a time. `nodes/{routing,skills,tier,memory}.py` are edited by `lead` in T003 (the `judgments_from_result` signature) and then by `bars`. `conversation/turn.py` belongs to `recorder`, including the ze-core tool sink, the deleted `on_tool_end` branch and the routing and memory partial fields (T007a); `tools` owns the ze-agents side (every `call_tool` return reaching `ctx.tool_sink`, delegate and flatten) and the committed rows in `nodes/trace.py`. `nodes/trace.py` belongs to `tools`; `bars` passes routing thresholds only through the envelope. The web lane builds against fixture traces with the generated types, so it starts after the contract step, not after the backend lanes. There is no JR lane: every piece crosses the engine's turn path or a contract.

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| In-process recorder keyed by thread, not graph state | A node that pauses for a confirmation never returns its state update, so stages and usage written to state would be lost for that run; a recorder outlives the pause. | Stage and usage reducers in `AgentState` (lose the paused node's run; need a per-turn reset sentinel). |
| `call_id` on tool calls | Parallel subtasks finish in any order, so a live position cannot equal the committed flattened index. | Live `call_index` (wrong under fan-out). |
| Node wrapper at build time | One place covers every node, overrides, plugin nodes and the workflow graph. | Timing from `astream_events` (no events on `ainvoke` resumes; no clean start time per node). |
