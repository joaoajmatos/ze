# Tasks: Trace Telemetry (187b)

**Input**: [spec.md](./spec.md) (clarifications 2026-10-18), [plan.md](./plan.md) (Lane Plan), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/trace-telemetry.md](./contracts/trace-telemetry.md), [quickstart.md](./quickstart.md).

**Tests**: required. **Fail-first**: write the test, run it, see it fail for the stated reason, then implement.

**Build gate**: 187 is on `main` (landed). Runs in parallel with the web phases; it touches only 187's trace instruments on the web side.

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[Lane]**: `[L:lead]`, `[L:recorder]`, `[L:tools]`, `[L:bars]`, `[L:web]`, `[L:docs]` (plan.md Lane Plan).
- **[Story]**: US1 stage times, US2 totals and usage, US3 routing and judgment bars, US4 truthful live tool and memory rows.

**Crew**: Sonnet `lead`, `recorder`, `tools`, `bars`, `web`; Haiku `docs`. Contract step first; `recorder`, `tools`, `bars` and `web` then run in parallel; `lead` merges `bars`, `tools`, `recorder`, then `web`. Tick a task's checkbox in the commit that finishes it.

**Rules**: no ze-core import from ze-agents; no Pydantic outside ze-api schemas; telemetry never raises into a turn (every recorder call guarded and logged); fake clocks in tests (patch the recorder's clock functions), never sleep; `git add <paths>`, never `-A` or `stash`.

---

## Phase 1: Setup

- [x] T001 [L:lead] Branch from `main` (29f7f307 or later). `make install && make web-install`; `graphify update .`; `graphify affected` on `MessageTrace`, `ToolCallTrace`, `JudgmentTrace`, `judgments_from_result`, `RoutingEnvelope`, `ToolCall`, `AgentContext`, `CostTracker`, `invoke_raw_turn`, `resume_turn`, `send_trace_partial`, `useTraceStore`. Grep `total_duration_ms`, `on_tool_end`, `pendingArrivals`, `arrivalsByMessage`, `sentAtByMessage`. Confirm the System One question ids in `routing/judge.py`, `ze_skills/judge.py`, `routing/tier.py` and `ze_worldstate/commitment_judge.py` against plan.md's bar maps, that the workflow graph builder adds nodes in one place, the park and resume sites that build `ParkedWrite` and `ApprovedCall` (`base_agent.py:578,950` on 29f7f307), and the exact sites in `api/ws/confirmation.py` and the cancel path that end a paused turn without a stamped reply. Record differences from plan.md "Blast radius" in the Handoffs note; stop and report differences to the Spec Architect (Lintel).

---

## Phase 2: Foundational (contract step, lane `lead`)

- [x] T002 [L:lead] Tests first: `core/engine/ze-core/tests/conversation/test_message_store.py` and `tests/orchestration/test_state_serde.py` (extend): a trace with the new fields (stages, usage, routing scores and thresholds, tool `call_id`/`start_offset_ms`, judgment `surface`/`bar`, `tool_duration_ms`, `turn_duration_ms`, `paused_ms`, `telemetry_partial`) round-trips through the store reader and the checkpoint serde; a stored trace with the old `total_duration_ms` and none of the new fields reads with `tool_duration_ms` 0 and the new fields empty or null; `core/contracts/ze-agents/tests/test_types.py`: two `ToolCall`s get different `call_id`s; `started_at` defaults to None; `ParkedWrite.trace_call_id` is a fresh uuid per park; a `ToolCall` with `call_id` and `started_at`, inside a `ParkedLoop.accumulated` list, survives the checkpoint serde round trip (`test_state_serde.py`); `AgentContext.tool_sink` defaults to None and is not in `repr`. Implement the dataclasses (plan.md "Design", data-model.md) in `messages/types.py`, `messages/store.py`, `routing/types.py` (`threshold`, `gap_threshold` with the `RouterConfig` defaults), `ze_agents/types.py`; rename `total_duration_ms` → `tool_duration_ms` in `ze_seed/narrative/loader.py:124`, the four keys in `ze_seed/narrative/persona.yaml` (1375, 1400, 1421, 1439) and every Python test listed in plan.md's blast radius. Add `core/ops/ze-seed/tests/test_narrative_traces.py`: a seeded trace has `tool_duration_ms` 1200 (not 0).
- [x] T003 [L:lead] Tests first: `apps/ze-api/tests/api/test_messages_route.py`, `test_judgments_trace_schema.py`, `test_schemas_rollback.py`, `test_sources_trace_schema.py` (extend or rename the field): the REST trace and the `WsTraceUpdateFrame` carry every new field, `total_duration_ms` is gone, and a trace without the new fields serializes with them null/empty; `send_trace_partial`'s base frame has `tool_duration_ms: 0`. Implement `api/v0/messages/{schemas,router}.py`, `api/ws/schemas.py`, `interface/native.py:146-169`. Change `judgments_from_result` to the plan's signature (`surface`, `bars`) and update its four callers (`nodes/routing.py`, `nodes/skills.py`, `nodes/tier.py`, `nodes/memory.py`) to pass their surface name and `bars={}` (lane `bars` fills the maps). Run `make codegen`, then rename the web sites in the same task so `make typecheck-web` stays green: `features/trace-state/lib/toTraceFrame.ts:20` and `toTraceFrame.test.ts:16,68,90`, `useTraceStore.test.ts:22`, `widgets/assemble/ui/trace/rows/ConductorRow.test.tsx:21`, `instruments/fixtures.ts:31`, `tools.test.ts:21`, `readouts.ts:31`. Delete `entities/message-trace/ui/MessageTracePanel.tsx` and its export from `entities/message-trace/index.ts` (no importer since 187; keep `useMessageTraceQuery`). Gates for the task: `make test-py`, `make test-web`, `make typecheck-web`. Commit the generated client with the task.
- [x] T004 [L:lead] Recorder stubs with final signatures: `ze_core/telemetry/turn.py` with `StageTiming`, `ModelUsage`, `TurnUsage`, `TurnTelemetry` (methods `record_stage`, `record_call`, `stamp`, attribute `emit`) whose methods do nothing and `stamp` returns the trace unchanged, `TurnTelemetryRegistry` (`start`, `resume`, `finish`), and the `current_turn_telemetry` ContextVar; a `turn_telemetry` registry attribute on `ze_core/container.py`'s `Container`. Test: `tests/telemetry/test_turn_stub.py` imports every name and the container has a registry. Lane `recorder` replaces the bodies.

**Checkpoint**: lanes start.

---

## Phase 3: User Story 1 - Stage times, live and from history (P1) 🎯 MVP

- [ ] T005 [L:recorder] [US1] Tests first `core/engine/ze-core/tests/telemetry/test_turn_telemetry.py` (fake `time.time` and `perf_counter`):
  - with the monotonic clock faked, `record_stage("fetch_context", started=t0+0.2, ended=t0+0.288)` gives `start_ms` 200, `duration_ms` 88, `run` 1; a wall-clock change (faked `time.time`) changes nothing;
  - `pause()` then `resume` 20 s later returns the same recorder, adds 20000 to `paused_ms` and sets `run` 2; `resume` with none creates one with `partial` true and no send target;
  - after `stamp`, `record_call` and `record_stage` change nothing (frozen);
  - `drain()` returns once the queue is empty or after 1 s in total, dropping what is left;
  - `emit` returns without awaiting the send; frames go out in order; with an interface whose send never returns, a turn of 17 stages finishes within 50 ms of its node time and each stuck frame is dropped after 1 s and logged; `finish` stops the sender;
  - `start` drops entries older than 30 minutes; `finish` removes the thread's entry;
  - every method swallows an internal exception and logs `turn_telemetry_failed`;
  - `emit` raising does not propagate.

  Implement `telemetry/turn.py` (stages part; usage in T007).
- [ ] T006 [L:recorder] [US1] Tests first `tests/orchestration/test_timing.py` and `tests/conversation/test_turn_telemetry_stamp.py` (fake graph with three nodes; interface mocked):
  - each node sends one partial `{"stages": [{name, start_ms, duration_ms, run}]}` in order;
  - a node that raises `GraphInterrupt` still records its stage;
  - with no recorder set, the wrapper only calls the node;
  - every node added by `build_graph` (including an override that is a sync function, one that is a `functools.partial`, and a plugin `pre_route_node`) and by the workflow graph builder is wrapped, and each wrapped node still receives `config`;
  - `invoke_raw_turn` stamps `final_state["message_trace"]` with the stage list, `turn_duration_ms` ≥ the sum of stages, and `paused_ms` 0;
  - an interrupted run keeps the recorder; `resume_turn` continues it, and the final trace holds the stages of both runs, with `run` 1 and 2 and `paused_ms` equal to the gap;
  - a turn that errors after `record_trace` still stores the stages reached;
  - one test through the real `build_graph`, compiled with an in-memory checkpointer, with a real `interrupt()` in `await_write_confirmation` and resumed with `Command(resume=...)` the way `resume_turn` does: the ContextVar reaches nodes run in LangGraph's tasks, `await_write_confirmation` appears once per run (LangGraph re-runs it from its start), and the stamped trace holds both runs;
  - the confirmation-timeout, superseded and cancel paths call `registry.finish` (no entry left behind);
  - ordering: with a slow first stage frame, `invoke_raw_turn` drains before it returns, so the committed trace is the last frame for the message;
  - a stage absent from the turn (decompose on a single-agent turn) is not in the list.
  - a Retry turn (165/180) on the same thread starts a fresh recorder; the replaced reply's stored stages are unchanged;
  - work scheduled with `fire_and_forget` after the stamp adds nothing to the stamped trace.

  Implement `orchestration/timing.py`, apply it in `orchestration/graph.py` and the workflow graph builder, wire `conversation/turn.py` (`registry.start`/`resume`/`finish`, `pause` on interrupt, the ContextVar, the send target from run 1, the stamp), and add the `finish` calls in `api/ws/confirmation.py` and the cancel path.

---

## Phase 4: User Story 2 - Turn total, tokens, cost, context fill (P1)

- [ ] T007 [L:recorder] [US2] Tests first `tests/telemetry/test_turn_usage.py` and `tests/telemetry/test_tracker.py` (extend):
  - `CostTracker.record` adds to the current recorder and still writes the cost record;
  - two calls to `anthropic/claude-sonnet-4-6` with prompts 5200 and 3920 and completions 300 and 110 give `calls` 2, `prompt_tokens` 9120, `completion_tokens` 410, `max_prompt_tokens` 5200, `cost_usd` from `estimate_cost_usd`, and `context_fill` 5200/200000;
  - a `typesafe/jev-20260917` call is counted in `system_one_tokens` and is never `main_model`;
  - an unknown model sets `estimated` true on its row and on the usage, and its `context_fill` uses the default window and may exceed 1;
  - a `record` with `audio_seconds` (transcription) is not in `usage`;
  - `main_model` is the tier's model when `state["tier"]` is set, else the routed agent's model;
  - `stamp` renames nothing: `tool_duration_ms` comes from `record_trace` (T009).

  Implement the usage part of `telemetry/turn.py`, `telemetry/tracker.py`, and the main-model choice in the stamp.

- [ ] T007a [L:recorder] [US4] Tests first `tests/conversation/test_tool_sink.py`: ze-core's sink (built in `invoke_raw_turn` and `resume_turn`, put in `config["configurable"]["tool_sink"]`) enqueues `{"tool_calls": [{call_id, name, agent, gate, start_offset_ms, duration_ms, success, result_snippet}]}`, with `start_offset_ms` from the monotonic `started_at`; a failed call reads `success: false` with its measured duration; the `on_tool_end` branch is gone; the embed_route partial carries `routing_scores` (top 9) and `routing_thresholds`; the memory partial carries `extraction_confidence` for fact chunks. Implement in `conversation/turn.py`.

---

## Phase 5: User Story 3 - Routing and judgment bars (P2)

- [ ] T010 [P] [L:bars] [US3] Tests first `core/engine/ze-core/tests/routing/test_router_thresholds.py`: every envelope the router builds (embedding, haiku fallback, forced, and the screen, preset and open-query envelopes built in their nodes) carries `threshold` and `gap_threshold` from `RouterConfig`; `embed_route`'s output envelope keeps `raw_scores`. Implement in `routing/router.py` and any node that builds an envelope (list them in the Handoffs note).
- [ ] T011 [L:bars] [US3] Tests first `tests/orchestration/nodes/test_judgment_bars.py`: with each surface configured, the trace rows carry `surface` and the bar per plan.md's maps (routing: `choice_trust`, `multi_specialist_hold`; skills: `choice_trust`, `needs_skill_hold`; complexity: `simple_max`; commitment intake: the six holds; `_outcome_row`: surface, no bar); with a surface's bars null (uncalibrated), the rows have `surface` set and `bar` null; a reloaded config changes the bar on the next turn only. Implement the bar maps in `nodes/{routing,skills,tier,memory}.py`.

---

## Phase 6: User Story 4 - Truthful live tool and memory rows (P2)

- [x] T008 [L:tools] [US4] Tests first `core/contracts/ze-agents/tests/test_call_tool_sink.py` and `tests/test_delegate_sink.py`:
  - every return path of `call_tool` (success, exception, unknown tool, refused, parked, denied, duplicate, pre-approved) hands exactly one `ToolCall` to `ctx.tool_sink`, with `started_at` (monotonic) set on the paths that ran the tool;
  - a sink that raises is logged and the call result is unchanged;
  - a parked call's `call_id` is its `ParkedWrite.trace_call_id`; the approved run on resume has the same `call_id`, so a park-then-approve gives one id; two delegates whose provider tool-call ids collide (both `call_0`) get different `call_id`s;
  - a delegate turn: `delegate_to_agent` passes `tool_sink` into `sub_ctx`; the specialist's calls reach the sink; the nested dict carries `call_id` and `started_at`, and `flatten_tool_calls` returns calls with the same `call_id` and `started_at` (no new uuid);
  - `execute_tool`, compound subtasks and delegates pass `tool_sink` into `AgentContext` beside `token_sink` (`execution.py:299,323,400,474`).

  Implement in `ze_agents/base_agent.py` (`_finish`, ids for parked and approved calls), `ze_agents/delegate.py`, `ze_agents/nested_tools.py` and `nodes/execution.py`.
- [x] T009 [L:tools] [US4] Tests first `tests/orchestration/nodes/test_record_trace.py` (extend): `tool_duration_ms` is the sum of tool durations; each committed tool row carries the `call_id` of its `ToolCall` and `start_offset_ms` from `started_at` against the recorder start (null with no recorder, with a `partial` recorder created by `resume()` after a simulated restart, or when out of range); a compound turn with two subtasks and a delegate turn: every committed row's `call_id` equals the id its live row carried (SC-003), and rows keep their flattened `call_index`; `routing_scores` is the top 9 of `raw_scores` by score, highest first, and empty for envelopes with a single forced score; `routing_thresholds` comes from the envelope. Implement in `nodes/trace.py`.

---

## Phase 7: Web instruments (US1–US4)

- [ ] T012 [L:web] Tests first `features/trace-state/lib/toTraceFrame.test.ts` (extend): a REST trace with `stages`, `usage`, `routing_scores`, `routing_thresholds`, `turn_duration_ms`, `paused_ms`, `telemetry_partial`, tool `call_id`/`start_offset_ms` and judgment `surface`/`bar` round-trips to the frame unchanged (the history path, `useSessionTraces.ts:28`). Then `features/trace-state/model/useTraceStore.test.ts` (extend): partial frames append `stages` in arrival order; tool rows merge by `call_id` (a second row with the same id replaces the first); a stage repeated with the same `(run, name, start_ms)` is kept once; a partial arriving after the message's committed trace is ignored (a slow first frame, then the commit); the store has no `pendingArrivals`, `arrivalsByMessage`, `pendingSentAt` or `sentAtByMessage`; a committed trace replaces the pending one with its server stages. Implement in `toTraceFrame.ts`, `useTraceStore.ts` (delete the arrival stamps and `stagesIn`) and any `useTraceSocket`/`useSessionTraces` caller of them.
- [ ] T013 [L:web] Tests first in `widgets/assemble/lib/instruments/{signal,readouts,routing,judgments,tools,memory}.test.ts` and `ui/trace/instruments.test.tsx` with fixture traces from the contract:
  - signal: stages in server order with offsets from `start_ms`, labelled per plan.md; a second run is drawn after a gap labelled with `paused_ms`; a trace from history shows the same offsets; a trace with no `stages` (before 187b) shows today's no-timing fallback; no function takes a client arrival time (SC-006);
  - readouts: total from `turn_duration_ms` ("partial" when `telemetry_partial`), active time = total − `paused_ms`, tool time from `tool_duration_ms`, tokens, cost and context fill from `usage` with "est." when estimated (a fill over 1 clamps the bar at full and shows the real number), System One tokens apart; null usage shows the model name only;
  - routing: one bar per `routing_scores` entry against `routing_thresholds`; an empty list shows the method;
  - judgments: each gauge marks its `bar`; `surface` with a null bar reads "uncalibrated";
  - tools: rows keyed by `call_id`, placed by `start_offset_ms`, a failed live row shows failed, a `gate: "parked"` row reads "waiting for you" and is replaced in place by its approved row;
  - memory: live fact chunks show extraction confidence.

  Implement in the six instrument modules and their `ui/trace` components.

---

## Phase 8: Polish and cross-cutting

- [ ] T014 [L:lead] Merge `bars`, `tools`, `recorder`, then `web`. `make codegen` if a schema moved. Gates: `make test-py`, `make test-web`, `make typecheck-web`, `make lint`. The quickstart grep returns nothing. Measure SC-004 with a realistic send (an interface that awaits a real local WebSocket, not a mock): the median server time of the turn tests with and without the recorder (record both numbers in the Handoffs note; over 5 ms is a finding for the Spec Architect).
- [ ] T015 [L:lead] Run [quickstart.md](./quickstart.md) steps 1–5 against `make dev-full`, with captures of the trace panel (live, from history, and the paused turn) at 1440, and record them in the Handoffs note.
- [ ] T016 [P] [L:docs] `docs/native-interface.md` (partial stage, tool and routing frames; best-effort live frames; committed fields; the rename), `docs/architecture.md` (the trace section and the timed-node note), `docs/frontend.md` (instruments read server stages; remove the arrival-stamp wording); doc-style skill.
- [ ] T017 [P] [L:docs] `AGENTS.md` phase row 187b and the repo-layout block (`telemetry/` names `turn.py`, `orchestration/` names `timing.py`); `specs/README.md` row 187b → Implemented; spec status.
- [ ] T018 [L:docs] Coverage check: `git diff main...HEAD --stat` against plan.md "Docs touched"; record in the Handoffs note.

---

## Dependencies & Execution Order

- T001 → T002 → T003 → T004 (contract) → lanes.
- `recorder`: T005 → T006 → T007 → T007a. `tools`: T008 → T009.
- `bars`: T010 → T011. `web`: T012 → T013.
- T014 after the three lanes; T015 after T014; T016–T017 after T015; T018 last.

## Parallel Example

```text
After the contract step:
  recorder: T005 → T006 → T007 → T007a
  tools:    T008 → T009
  bars:     T010 → T011
  web:      T012 → T013
```

## Implementation Strategy

- MVP = US1 (server stage times, live and stored) on the contract step, with the signal path reading them. US2 completes the readouts. US3 and US4 make the remaining instruments honest.
