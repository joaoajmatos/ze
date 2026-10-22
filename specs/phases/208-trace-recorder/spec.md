# Feature Specification: Trace Recorder

**Feature Branch**: `208-trace-recorder`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 200, 201, 207 (207's turn module owns `ws/turns.py` and `ws/rollback_state.py` and reports the superseded rows and the rollback section to the recorder)

**Input**: Architecture review 2026-10-22, candidate C5: one trace recorder per turn, and one trace schema on both transports. Extend `TurnTelemetry` into the single recorder. Each node reports its section through `timed()`. The recorder projects each section once, and `trace_update` carries the same payload as REST. The reply rewrites (declined lines, loop offer) move out of `record_trace`.

**Governed by**: phase 89 (message trace), phase 95 (streamed partial traces), phase 187b (trace telemetry: one `TurnTelemetry` per turn, `timed()` on every node, the ordered non-blocking sender, "the committed trace is the complete record"), `specs/arch/langgraph-orchestration.md` (graph state is checkpointed; services arrive at invocation time), `specs/arch/pre-v1-hard-cuts.md`, `specs/GLOSSARY.md` (Trace, Turn, Thread).

**Doctrine functions served**: governance (the trace is Ze's honesty surface: what the user reads about a reply must be what happened in that turn, the same live and later).

**Owning packages** (for planning): ze-core (`orchestration/nodes/trace.py`, `nodes/memory.py` trace patch, `conversation/turn.py` partials and stamp, `telemetry/turn.py`, `orchestration/timing.py`, `conversation/messages/types.py`), ze-api (`interface/native.py` trace frames, `api/v0/messages/router.py` and `schemas.py`, `api/ws/schemas.py`; the two WS-layer patches in `ws/turns.py` and `ws/rollback_state.py` are coordinated with phase 207), ze-client (regenerated types), ze-web (`features/trace-state`). No migration: the stored trace JSON keeps its shape, apart from fields this phase deletes.

## Context

This is a deepening refactor. Its users are the maintainers who add a trace field, and the person reading the trace panel. The guarantee it protects is one the user sees: the trace of a reply says what happened in that turn, and it reads the same while the reply streams, when it lands, and when the thread is reopened later.

Facts checked on 2026-10-22 (commit `c8dc97da`):

**The committed trace is assembled in five places, in sequence:**

1. `record_trace` builds `MessageTrace` from `AgentState` (`ze_core/orchestration/nodes/trace.py:58-138`).
2. `write_memory` runs after it and replaces the trace to append judgment rows from the commitment intake or the fact judge (`nodes/memory.py:157-205`, returned at `:256`).
3. `invoke_raw_turn` and `resume_turn` stamp telemetry onto it after the graph ends: stages, durations, usage (`conversation/turn.py:187-198`, `TurnTelemetry.stamp` at `telemetry/turn.py:194`).
4. The WS turn handler appends `superseded` confirmation rows (`ze_api/api/ws/turns.py:219-240`).
5. The Retry path sets `trace.rollback` (`ze_api/api/ws/rollback_state.py:134`).

The review counted four places; it missed the rollback patch.

**Node order makes the trace describe the wrong turn.** `record_trace` reads `compaction_span` (`trace.py:79`) before `write_memory` sets it for this turn (`memory.py:286`, `:292`). So the trace reports the previous turn's compaction: bug B6. Phase 198 patches the symptom. The cause is that a node can only report to the trace by leaving a field in graph state for a later node to copy, and only the order of nodes decides whether the copy happens in time.

**The trace is projected four times, by hand, with rules that have drifted:**

- **Live partials** are built in `invoke_raw_turn` by matching node names in the event stream: `embed_route`, `resolve_screen`, `choose_tier` and `fetch_context` (`turn.py:302-354`). Each branch writes its own dictionary. Routing thresholds are always sent, even when the envelope has none; the committed trace sends `null` instead (`trace.py:351-356`). Memory chunks are sent only when there are some.
- **Two send paths.** Those four partials go straight to `interface.send_trace_partial` and are awaited. Stage rows (`timing.py:51-57`) and live tool rows (`turn.py:216-248`) go through the recorder's ordered, non-blocking queue (`telemetry/turn.py:216-264`). Only the queue drops a frame that is stuck for 1 s, and only the queue is drained before the committed trace goes out.
- **Every partial frame is padded** with hand-written defaults for nine required fields (`ze_api/interface/native.py:148-171`: `agent: ""`, `confidence: 0.0`, and so on), so a partial cannot be told apart from a committed trace by its fields.
- **The committed WS frame** is `asdict(trace)` with the undo arguments removed (`native.py:45-57`, `:212-221`).
- **REST** maps the same dataclass field by field (`api/v0/messages/router.py:88` onwards, `_trace_to_response`).
- **The web app** converts a REST trace back into a WS frame for history, field by field, and casts the result (`apps/ze-web/src/features/trace-state/lib/toTraceFrame.ts:8-40`, `as WsTraceUpdateFrame`). It drops `procedure`, `effects_known` and `input`. So a voice turn, or a turn that invoked a procedure, shows those sections live and loses them when the thread is reopened.

**The schemas already agree; the code that fills them does not.** `MessageTrace` (`ze_core/conversation/messages/types.py:291`), `MessageTraceResponse` (`api/v0/messages/schemas.py:251`) and `WsTraceUpdateFrame` (`api/ws/schemas.py:152`) have the same fields, except `loop_offer_ids`, which the WS frame lacks. The review implied the two transports had different schemas. They do not. They are two hand-kept copies of one list, and `WsTraceUpdateFrame` is referenced only by tests: no server code builds or checks a frame against it.

**`record_trace` also rewrites the reply.** It appends "Okay, I didn't …" lines for declined writes (`_with_declined_lines`, `trace.py:189-203`) and the loop-offer line (`trace.py:120-137`), and returns a new `final_response`. A node named for the trace decides the reply text.

**Conductor state is read from two copies.** `_conductor_ledger` prefers the agent context's copy and falls back to the state's (`trace.py:332-337`). Phase 200 makes the child-run outcome the one source. This phase consumes it.

**Blast radius** (`graphify affected … --depth 2`, 2026-10-22):

| Symbol | Source references | Test references |
|---|---|---|
| `MessageTrace` | 16 files: ze-core (`conversation/{turn,retry,rollback}.py`, `messages/store.py`, `nodes/trace.py`, `timing.py`, `telemetry/{turn,tracker}.py`, `container.py`), ze-api (`messages/router.py`, `messages/views.py`, `ws/turns.py`), ze-seed (`narrative/loader.py`) | 281 |
| `record_trace` | `orchestration/graph.py`, `nodes/__init__.py` | 102 |
| `TurnTelemetry` | ze-core `turn.py`, `telemetry/turn.py`, `container.py`; ze-api `eval/router.py`, `ws/confirmation.py`, `ws/turns.py`, `wiring/container.py` | 36 |
| `MessageTraceResponse` | `api/v0/messages/router.py`, `api/v0/__init__.py` | 24 |
| `WsTraceUpdateFrame` | none | 19 |
| `toTraceFrame` | `trace-state/model/useSessionTraces.ts`, `widgets/assemble/model/useAssemble.ts` | 1 |

## Clarifications

### Session 2026-10-22

- Q: Where do the reply rewrites (declined-write lines, loop-offer line) move? → A: To a graph step that finishes the reply. It runs after execution (and synthesis) and before the trace is recorded and before `write_memory`, so the reply stored in history is the reply the user sees (FR-009).
- Q: What does a partial frame carry? → A: Only the sections reported so far, each typed like the matching committed field, and marked partial. Frames are not cumulative; the client merges them, as `useTraceStore` does today (FR-006).
- Q: What is the order between 208 and 207? → A: 208 depends on 207. Phase 207's turn module reports the superseded confirmation rows and the rollback section to the recorder; this phase provides the call and does not edit the WS turn files itself (FR-010).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The trace describes the turn it belongs to (Priority: P1)

The user opens the trace for a reply. Every section describes that turn: the compaction, the judgments, the tools, the stages. No section comes from the previous turn because a node ran in a different order.

**Why this priority**: B6 is a trace that reports the wrong turn. The trace is the honesty surface; a wrong trace is worse than a missing one.

**Independent Test**: A whole-turn test runs two turns through the real graph. The second turn compacts and the first does not. The second turn's committed trace shows the compaction and the first turn's does not. The test does not depend on the order of nodes in the graph.

**Acceptance Scenarios**:

1. **Given** a turn in which history is compacted, **When** its trace is committed, **Then** the trace shows that compaction, and the next turn's trace shows none unless it also compacted.
2. **Given** a turn whose commitment intake writes judgment rows, **When** the trace is committed, **Then** those rows are in it without any node replacing the trace after it was built.
3. **Given** any node that reports a trace section, **When** a maintainer moves that node earlier or later in the graph, **Then** the committed trace is unchanged.

---

### User Story 2 - Live and committed traces agree (Priority: P1)

While a reply streams, the trace panel fills section by section. When the reply lands, the committed trace replaces the partial one. Nothing the user saw while it streamed changes value, unless the turn itself changed it (for example, a later stage), and nothing that only the committed trace knows is missing from it.

**Why this priority**: Today the partials are a separate projection that disagrees with the committed trace (routing thresholds, padded defaults), so the panel can visibly change when the reply lands for no reason in the turn.

**Independent Test**: A whole-turn test collects every partial frame and the committed frame of one turn. For each section, the last partial value equals the committed value.

**Acceptance Scenarios**:

1. **Given** a routed turn whose envelope has no thresholds, **When** the routing section streams and the trace is committed, **Then** both show no thresholds.
2. **Given** a partial frame, **When** the client reads it, **Then** it can tell which sections the frame carries; sections not yet reported are absent, not filled with defaults.
3. **Given** a turn that pauses for a write confirmation and resumes, **When** the trace is committed, **Then** the sections from before the pause and after it are all present once.

---

### User Story 3 - A reopened thread shows the same trace (Priority: P1)

The user reopens a thread from yesterday and opens the trace of a voice reply that invoked a procedure. It shows the input section and the procedure section, exactly as it did live.

**Why this priority**: Today the history path drops `procedure`, `effects_known` and `input`, so the record the user trusts is less complete than the live view.

**Independent Test**: For one fully populated trace, the REST payload and the committed WS payload are equal field for field (apart from frame envelope fields such as `type`, `message_id` and `thread_id`), and the web app renders the REST payload through the same path as the live one, with no conversion step.

**Acceptance Scenarios**:

1. **Given** a committed trace with every section filled, **When** the web app loads it from REST, **Then** every section the live view showed is shown.
2. **Given** a new trace field, **When** a maintainer adds it, **Then** it reaches REST, the WS frame and the web types with one edit to the trace type, plus its rendering.

---

### User Story 4 - The reply is decided before the trace records it (Priority: P2)

The declined-write lines and the loop-offer line are added to the reply by a step whose job is the reply, before the trace records the turn. The trace records the final reply text; it never changes it.

**Why this priority**: A trace builder that rewrites the reply hides reply rules in the wrong place, and the trace cannot be built from reports alone while it also edits what it reports on.

**Independent Test**: A turn with one declined write and one loop offer ends with both lines in the reply. The trace recorder's code has no path that returns a reply.

**Acceptance Scenarios**:

1. **Given** the user declined a parked write and the reply does not say so, **When** the turn ends, **Then** the reply carries "Okay, I didn't …" for it, as today.
2. **Given** a loop offer this turn, **When** the turn ends, **Then** the reply carries the offer line, as today.
3. **Given** a reply that gained a declined-write line, **When** the next turn reads the thread's history, **Then** the history holds the reply with that line, as today.

---

### Edge Cases

- **Paused turns.** A confirmation pause ends one graph run and a resume starts another, possibly after a restart. The recorder already survives a pause in-process (phase 187b) and marks itself partial after a restart. The sections reported in the first run must reach the committed trace in both cases. Where the in-process recorder is gone after a restart, sections that live in checkpointed state are still recovered; telemetry stays `telemetry_partial`, as today.
- **Superseded confirmations and rollback.** These are known only to the WS layer, after the graph ends. They must reach the trace through the recorder before it is saved, not by mutating a built trace. The turn module of phase 207 is the caller.
- **Graph error or empty reply.** A turn that errors still commits whatever sections were reported, as long as an envelope exists (today `record_trace` returns nothing without an envelope).
- **Workflow graph.** The workflow graph reuses the engine nodes. Its runs commit no message trace today. They report sections to a recorder that is discarded, or to none; either way, no node may fail because no recorder is present.
- **Eval turns.** The eval route returns no trace today, and ze-eval reads none. Eval turns still build one through the same recorder, so the whole-turn tests can drive the eval path.
- **Undo arguments.** Today's rule holds: the undo arguments stay on the server, in neither the WS frame nor REST.
- **Frames that cannot be sent.** A partial that cannot be serialized or sent is dropped and logged; the turn and the committed trace are unaffected (phase 117 rule).
- **Seed data.** `ze-seed` builds `MessageTrace` objects for dev data. It keeps building the same type.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each turn MUST have one trace recorder. Every node that contributes to the trace MUST report its section to that recorder, and no node MUST replace or patch a trace another node built.
- **FR-002**: The committed trace MUST be built by the recorder from the reported sections at the end of the turn, after every node that reports has run. Its content MUST NOT depend on the order of nodes in the graph.
- **FR-003**: The compaction section and the judgment rows of a turn MUST come from that turn (B6 cannot recur by construction). Phase 198's regression test MUST stay.
- **FR-004**: Live partial frames MUST be produced by the recorder from the same section values that go into the committed trace. The engine's turn entry points MUST NOT match node names to build partials.
- **FR-005**: All trace frames, partial and committed, MUST leave the server through one ordered path, and that path MUST be drained before the committed frame is sent.
- **FR-006**: A partial frame MUST carry only the sections reported since the previous frame, each typed like the matching field of the committed trace, and MUST be marked partial. Partial frames MUST NOT be cumulative and MUST NOT fill sections they do not carry with placeholder defaults.
- **FR-007**: The committed `trace_update` frame and the REST trace MUST carry one payload type, defined once. `loop_offer_ids` MUST be on both. The server MUST build the frame from that type, so the WS schema is no longer a hand-kept copy.
- **FR-008**: The web app MUST render a trace loaded from REST through the same path as a live one, with no field-by-field conversion. `toTraceFrame` MUST be deleted, and history MUST show `procedure`, `effects_known` and `input`.
- **FR-009**: The declined-write lines and the loop-offer line MUST be added to the reply by a graph step that finishes the reply. It MUST run after execution and synthesis and before the trace is recorded and before `write_memory`, with today's wording and conditions. The recorder MUST NOT change `final_response` or `agent_result`.
- **FR-010**: The recorder MUST offer one call to report the superseded confirmation rows and the rollback section before the trace is saved. Phase 207's turn module is its caller. After this phase, code MUST NOT mutate a built trace; the two WS-layer patches (`ws/turns.py`, `ws/rollback_state.py`) are gone by then, replaced by phase 207's calls.
- **FR-011**: The conductor section MUST come from the single child-run outcome defined by phase 200. The fallback between two copies (`trace.py:332-337`) MUST be deleted.
- **FR-012**: Undo arguments MUST stay server-side, in neither transport.
- **FR-013**: A section a node fails to report MUST NOT fail the turn; it is absent from the trace and logged (today's "telemetry never breaks a turn" rule).
- **FR-014**: Behaviour MUST NOT change otherwise. The trace section values, reply text and stored trace JSON MUST match today's for the existing ze-core, ze-api and ze-web trace suites, apart from the fixed drifts listed here (B6, routing thresholds, padded partials, the three fields lost in history, `loop_offer_ids` on WS).

### Key Entities

- **Trace recorder**: the one object per turn that collects sections, sends partial frames and builds the committed trace. Today's `TurnTelemetry` grows into it; it already survives a confirmation pause.
- **Trace section**: one part of the trace that one node owns: routing, screen, tier, memory, tools, judgments, conductor, compaction and recap, skills, workspace, procedure, write confirmations, rollback, input, timing and usage. It has one type, used in partial frames, the committed trace and REST.
- **Partial frame**: a live frame carrying the sections reported so far.
- **Committed trace**: the complete trace of one reply, stored with the message and sent once.
- **Reply finishing step**: the graph step, after execution and synthesis, that adds the declined-write and loop-offer lines to the reply before the trace records it and before the reply enters history.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: One whole-turn test per turn shape (single, compound, delegated, paused-and-resumed, compacted, preset) passes: for every section, the last partial value equals the committed value.
- **SC-002**: The committed trace is built in one place, down from five.
- **SC-003**: Adding a trace field edits the trace type and its renderer only, down from four places today (dataclass, REST mapping, WS schema, web conversion, plus their tests).
- **SC-004**: A reopened thread shows 100% of the sections the live trace showed, for a trace with every section filled (today 3 of 32 fields are lost).
- **SC-005**: 0 node-name matches in the turn entry points (down from 4) and 0 trace mutations outside the recorder (down from 4).

## Assumptions

- Phase 200 has landed: conductor and procedure state come back from a child run in one value, and the per-turn reset is generated. Phase 201 has landed: the recorder and the interface reach nodes through typed turn services and the turn request, not string keys.
- Phase 198 has patched B6. This phase replaces the patch with the mechanism and keeps the test.
- Phase 207 (turn module) has landed and owns `ws/turns.py` and `ws/rollback_state.py`. If 207's turn module still patches the built trace when 208 starts, 208's plan switches those two call sites to the recorder's call, and changes nothing else in them.
- The recorder stays in ze-core, in process, keyed by thread (phase 187b's registry). Checkpointing it is out of scope.
- The trace panel's rendering and the trace instruments of phase 187 do not change, except that they read the REST type directly.
- The stored trace JSON (`messages.trace`) keeps its shape; no migration. Old rows that lack `loop_offer_ids` already default to empty.
- Out of scope: the honesty guards and the reply template of phase 209 (they act inside the agent; the reply finishing step here acts on graph-level outcomes); the judgment record of phase 202 (this phase only moves where its rows are reported); and the web turn state of phase 205.
