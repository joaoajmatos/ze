# Tasks: Trace Telemetry (187b)

**Input**: [spec.md](./spec.md) (clarifications 2026-10-18), [plan.md](./plan.md) (Lane Plan), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/trace-telemetry.md](./contracts/trace-telemetry.md), [quickstart.md](./quickstart.md).

**Tests**: required. **Fail-first**: write the test, run it, see it fail for the stated reason, then implement.

**Build gate**: 187 is on `main` (landed). Runs in parallel with the web phases; it touches only 187's trace instruments on the web side.

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[Lane]**: `[L:lead]`, `[L:recorder]`, `[L:bars]`, `[L:web]`, `[L:docs]` (plan.md Lane Plan).
- **[Story]**: US1 stage times, US2 totals and usage, US3 routing and judgment bars, US4 truthful live tool and memory rows.

**Crew**: Sonnet `lead`, `recorder`, `bars`, `web`; Haiku `docs`. Contract step first; `recorder`, `bars` and `web` then run in parallel; `lead` merges `bars`, `recorder`, then `web`. Tick a task's checkbox in the commit that finishes it.

**Rules**: no ze-core import from ze-agents; no Pydantic outside ze-api schemas; telemetry never raises into a turn (every recorder call guarded and logged); fake clocks in tests (patch the recorder's clock functions), never sleep; `git add <paths>`, never `-A` or `stash`.

---

## Phase 1: Setup

- [ ] T001 [L:lead] Branch from `main`. `make install && make web-install`; `graphify update .`; `graphify affected` on `MessageTrace`, `ToolCallTrace`, `JudgmentTrace`, `judgments_from_result`, `RoutingEnvelope`, `ToolCall`, `AgentContext`, `CostTracker`, `invoke_raw_turn`, `resume_turn`, `send_trace_partial`, `useTraceStore`. Grep `total_duration_ms`, `on_tool_end`, `pendingArrivals`, `arrivalsByMessage`, `sentAtByMessage`. Confirm the System One question ids in `routing/judge.py`, `ze_skills/judge.py`, `routing/tier.py` and `ze_worldstate/commitment_judge.py` against plan.md's bar maps, and that the workflow graph builder adds nodes in one place. Record differences from plan.md "Blast radius" in the Handoffs note; stop and report differences to the Spec Architect (Lintel).

---

## Phase 2: Foundational (contract step, lane `lead`)

- [ ] T002 [L:lead] Tests first: `core/engine/ze-core/tests/conversation/test_message_store.py` and `tests/orchestration/test_state_serde.py` (extend): a trace with the new fields (stages, usage, routing scores and thresholds, tool `call_id`/`start_offset_ms`, judgment `surface`/`bar`, `tool_duration_ms`, `turn_duration_ms`, `paused_ms`, `telemetry_partial`) round-trips through the store reader and the checkpoint serde; a stored trace with the old `total_duration_ms` and none of the new fields reads with `tool_duration_ms` 0 and the new fields empty or null; `core/contracts/ze-agents/tests/test_types.py`: two `ToolCall`s get different `call_id`s; `started_at` defaults to None; `AgentContext.tool_sink` defaults to None and is not in `repr`. Implement the dataclasses (plan.md "Design", data-model.md) in `messages/types.py`, `messages/store.py`, `routing/types.py` (`threshold`, `gap_threshold` with the `RouterConfig` defaults), `ze_agents/types.py`; rename `total_duration_ms` → `tool_duration_ms` in `ze_seed/narrative/loader.py:124` and every test listed in plan.md's blast radius.
- [ ] T003 [L:lead] Tests first: `apps/ze-api/tests/api/test_messages_route.py`, `test_judgments_trace_schema.py`, `test_schemas_rollback.py`, `test_sources_trace_schema.py` (extend or rename the field): the REST trace and the `WsTraceUpdateFrame` carry every new field, `total_duration_ms` is gone, and a trace without the new fields serializes with them null/empty; `send_trace_partial`'s base frame has `tool_duration_ms: 0`. Implement `api/v0/messages/{schemas,router}.py`, `api/ws/schemas.py`, `interface/native.py:146-169`. Change `judgments_from_result` to the plan's signature (`surface`, `bars`) and update its four callers (`nodes/routing.py`, `nodes/skills.py`, `nodes/tier.py`, `nodes/memory.py`) to pass their surface name and `bars={}` (lane `bars` fills the maps). Run `make codegen`; commit the generated client with the task.
- [ ] T004 [L:lead] Recorder stubs with final signatures: `ze_core/telemetry/turn.py` with `StageTiming`, `ModelUsage`, `TurnUsage`, `TurnTelemetry` (methods `record_stage`, `record_call`, `stamp`, attribute `emit`) whose methods do nothing and `stamp` returns the trace unchanged, `TurnTelemetryRegistry` (`start`, `resume`, `finish`), and the `current_turn_telemetry` ContextVar; a `turn_telemetry` registry attribute on `ze_core/container.py`'s `Container`. Test: `tests/telemetry/test_turn_stub.py` imports every name and the container has a registry. Lane `recorder` replaces the bodies.

**Checkpoint**: lanes start.

---

## Phase 3: User Story 1 - Stage times, live and from history (P1) 🎯 MVP

- [ ] T005 [L:recorder] [US1] Tests first `core/engine/ze-core/tests/telemetry/test_turn_telemetry.py` (fake `time.time` and `perf_counter`):
  - `record_stage("fetch_context", started_wall=t0+0.2, duration_s=0.088)` gives `start_ms` 200, `duration_ms` 88, `run` 1;
  - a wall clock moved backwards mid-turn gives `start_ms` 0, never negative;
  - `resume` returns the same recorder, adds the gap to `paused_ms` and sets `run` 2; `resume` with none creates one with `partial` true;
  - `start` drops entries older than 30 minutes; `finish` removes the thread's entry;
  - every method swallows an internal exception and logs `turn_telemetry_failed`;
  - `emit` raising does not propagate.

  Implement `telemetry/turn.py` (stages part; usage in T007).
- [ ] T006 [L:recorder] [US1] Tests first `tests/orchestration/test_timing.py` and `tests/conversation/test_turn_telemetry_stamp.py` (fake graph with three nodes; interface mocked):
  - each node sends one partial `{"stages": [{name, start_ms, duration_ms, run}]}` in order;
  - a node that raises `GraphInterrupt` still records its stage;
  - with no recorder set, the wrapper only calls the node;
  - every node added by `build_graph` (including an override and a plugin `pre_route_node`) and by the workflow graph builder is wrapped;
  - `invoke_raw_turn` stamps `final_state["message_trace"]` with the stage list, `turn_duration_ms` ≥ the sum of stages, and `paused_ms` 0;
  - an interrupted run keeps the recorder; `resume_turn` continues it, and the final trace holds the stages of both runs, with `run` 1 and 2 and `paused_ms` equal to the gap;
  - a turn that errors after `record_trace` still stores the stages reached;
  - a stage absent from the turn (decompose on a single-agent turn) is not in the list.
  - a Retry turn (165/180) on the same thread starts a fresh recorder; the replaced reply's stored stages are unchanged;
  - work scheduled with `fire_and_forget` after the stamp adds nothing to the stamped trace.

  Implement `orchestration/timing.py`, apply it in `orchestration/graph.py` and the workflow graph builder, and wire `conversation/turn.py` (`registry.start`/`resume`/`finish`, the ContextVar, `emit` to `send_trace_partial`, the stamp).

---

## Phase 4: User Story 2 - Turn total, tokens, cost, context fill (P1)

- [ ] T007 [L:recorder] [US2] Tests first `tests/telemetry/test_turn_usage.py` and `tests/telemetry/test_tracker.py` (extend):
  - `CostTracker.record` adds to the current recorder and still writes the cost record;
  - two calls to `anthropic/claude-sonnet-4-6` with prompts 5200 and 3920 and completions 300 and 110 give `calls` 2, `prompt_tokens` 9120, `completion_tokens` 410, `max_prompt_tokens` 5200, `cost_usd` from `estimate_cost_usd`, and `context_fill` 5200/200000;
  - a `typesafe/jev-20260917` call is counted in `system_one_tokens` and is never `main_model`;
  - an unknown model sets `estimated` true on its row and on the usage;
  - `main_model` is the tier's model when `state["tier"]` is set, else the routed agent's model;
  - `stamp` renames nothing: `tool_duration_ms` comes from `record_trace` (T009).

  Implement the usage part of `telemetry/turn.py`, `telemetry/tracker.py`, and the main-model choice in the stamp.

---

## Phase 5: User Story 3 - Routing and judgment bars (P2)

- [ ] T010 [P] [L:bars] [US3] Tests first `core/engine/ze-core/tests/routing/test_router_thresholds.py`: every envelope the router builds (embedding, haiku fallback, forced, and the screen, preset and open-query envelopes built in their nodes) carries `threshold` and `gap_threshold` from `RouterConfig`; `embed_route`'s output envelope keeps `raw_scores`. Implement in `routing/router.py` and any node that builds an envelope (list them in the Handoffs note).
- [ ] T011 [L:bars] [US3] Tests first `tests/orchestration/nodes/test_judgment_bars.py`: with each surface configured, the trace rows carry `surface` and the bar per plan.md's maps (routing: `choice_trust`, `multi_specialist_hold`; skills: `choice_trust`, `needs_skill_hold`; complexity: `simple_max`; commitment intake: the six holds; `_outcome_row`: surface, no bar); with a surface's bars null (uncalibrated), the rows have `surface` set and `bar` null; a reloaded config changes the bar on the next turn only. Implement the bar maps in `nodes/{routing,skills,tier,memory}.py`.

---

## Phase 6: User Story 4 - Truthful live tool and memory rows (P2)

- [ ] T008 [L:recorder] [US4] Tests first `core/contracts/ze-agents/tests/test_call_tool_sink.py` and `core/engine/ze-core/tests/conversation/test_tool_sink.py`:
  - every return path of `call_tool` (success, exception, unknown tool, refused, parked, denied, duplicate, pre-approved) hands exactly one `ToolCall` to `ctx.tool_sink`, with `started_at` set on the paths that ran the tool;
  - a sink that raises is logged and the call result is unchanged;
  - ze-core's sink emits `{"tool_calls": [{call_id, name, agent, start_offset_ms, duration_ms, success, result_snippet}]}` with a failed call reported as `success: false` and its measured duration;
  - the `on_tool_end` branch is gone (no partial with `duration_ms: 0` and `success: true` for a failed call);
  - `execute_tool`, subtasks and delegates pass `tool_sink` into `AgentContext` beside `token_sink`;
  - the memory partial carries `extraction_confidence` for fact chunks.

  Implement in `ze_agents/base_agent.py` (`_finish`), `conversation/turn.py` (sink, delete `on_tool_end`, memory partial) and `nodes/execution.py`.
- [ ] T009 [L:recorder] [US4] Tests first `tests/orchestration/nodes/test_record_trace.py` (extend): `tool_duration_ms` is the sum of tool durations; each committed tool row carries the `call_id` of its `ToolCall` and `start_offset_ms` from `started_at` against the recorder start (null with no recorder); a compound turn's rows keep their flattened `call_index` and their own ids; `routing_scores` is the top 9 of `raw_scores` by score, highest first, and empty for envelopes with a single forced score; `routing_thresholds` comes from the envelope. Implement in `nodes/trace.py`; the embed_route partial in `turn.py` adds the same `routing_scores` and `routing_thresholds`.

---

## Phase 7: Web instruments (US1–US4)

- [ ] T012 [L:web] Tests first `features/trace-state/model/useTraceStore.test.ts` (extend): partial frames append `stages` in arrival order; tool rows merge by `call_id` (a second row with the same id replaces the first); the store has no `pendingArrivals`, `arrivalsByMessage`, `pendingSentAt` or `sentAtByMessage`; a committed trace replaces the pending one with its server stages. Implement in `useTraceStore.ts` (delete the arrival stamps and `stagesIn`) and any `useTraceSocket`/`useSessionTraces` caller of them.
- [ ] T013 [L:web] Tests first in `widgets/assemble/lib/instruments/{signal,readouts,routing,judgments,tools,memory}.test.ts` and `ui/trace/instruments.test.tsx` with fixture traces from the contract:
  - signal: stages in server order with offsets from `start_ms`, labelled per plan.md; a second run is drawn after a gap labelled with `paused_ms`; a trace from history shows the same offsets; a trace with no `stages` (before 187b) shows today's no-timing fallback; no function takes a client arrival time (SC-006);
  - readouts: total from `turn_duration_ms` ("partial" when `telemetry_partial`), tool time from `tool_duration_ms`, tokens, cost and context fill from `usage` with "est." when estimated, System One tokens apart; null usage shows the model name only;
  - routing: one bar per `routing_scores` entry against `routing_thresholds`; an empty list shows the method;
  - judgments: each gauge marks its `bar`; `surface` with a null bar reads "uncalibrated";
  - tools: rows keyed by `call_id`, placed by `start_offset_ms`, a failed live row shows failed;
  - memory: live fact chunks show extraction confidence.

  Implement in the six instrument modules and their `ui/trace` components.

---

## Phase 8: Polish and cross-cutting

- [ ] T014 [L:lead] Merge `bars`, `recorder`, then `web`. `make codegen` if a schema moved. Gates: `make test-py`, `make test-web`, `make typecheck-web`, `make lint`. The quickstart grep returns nothing. Measure SC-004: the turn tests' median server time with and without the recorder (record both numbers in the Handoffs note; over 5 ms is a finding for the Spec Architect).
- [ ] T015 [L:lead] Run [quickstart.md](./quickstart.md) steps 1–5 against `make dev-full`, with captures of the trace panel (live, from history, and the paused turn) at 1440, and record them in the Handoffs note.
- [ ] T016 [P] [L:docs] `docs/native-interface.md` (partial stage, tool and routing frames; committed fields; the rename), `docs/architecture.md` (the trace section and the timed-node note), `docs/frontend.md` (instruments read server stages); doc-style skill.
- [ ] T017 [P] [L:docs] `AGENTS.md` phase row 187b; `specs/README.md` row 187b → Implemented; spec status.
- [ ] T018 [L:docs] Coverage check: `git diff main...HEAD --stat` against plan.md "Docs touched"; record in the Handoffs note.

---

## Dependencies & Execution Order

- T001 → T002 → T003 → T004 (contract) → lanes.
- `recorder`: T005 → T006 → T007; T008 → T009 (T008 after T006, since both edit `turn.py`).
- `bars`: T010 → T011. `web`: T012 → T013.
- T014 after the three lanes; T015 after T014; T016–T017 after T015; T018 last.

## Parallel Example

```text
After the contract step:
  recorder: T005 → T006 → T007 → T008 → T009
  bars:     T010 → T011
  web:      T012 → T013
```

## Implementation Strategy

- MVP = US1 (server stage times, live and stored) on the contract step, with the signal path reading them. US2 completes the readouts. US3 and US4 make the remaining instruments honest.
