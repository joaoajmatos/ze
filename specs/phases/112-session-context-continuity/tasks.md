---

description: "Task list for Session Context Continuity"
---

# Tasks: Session Context Continuity

**Input**: Design documents from `/specs/phases/112-session-context-continuity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/graph-nodes.md,
contracts/trace-schema.md, quickstart.md (all present)

**Tests**: Not explicitly requested as a separate ask in the feature spec, but CLAUDE.md's
Test Discipline and the constitution's Principle V (NON-NEGOTIABLE) require unit tests
for every new/changed unit with no real DB/LLM; test tasks below are mandatory, not
optional.

**Organization**: Tasks are grouped by user story (P1 → P2 → P3) per spec.md.
**Correction from planning** (see plan.md Summary, research.md R1): the spec's premise of
"currently unbounded `AgentState.messages` growth" does not match the code —
`write_memory` already hard-caps `state["messages"]` at the last `SESSION_HISTORY_LIMIT`
(10) entries every turn, and `fetch_context` already blanks history to `[]` on a long
gap. This task list replaces those two behaviors in place rather than adding new graph
nodes. Confirmed with the user before task generation.
**Corrections from `/speckit-analyze`**: T004/T005 dropped invalid/contradictory `[P]`
and story-label markers; T019/T020 no longer marked `[P]` (they share a test file);
T022A added to close the FR-012 composability coverage gap (compaction and resume
recap must both apply to the same turn without either discarding the other).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact — this feature touches two existing packages, no new package

## Path Conventions

Existing monorepo packages (see plan.md's Project Structure) — no new package created:
`core/ze-core/`, `core/ze-agents/`

---

## Phase 1: Setup

**Purpose**: Confirm the environment this feature builds on. No new package, no new
third-party dependency (research.md R3/R4 — static table + chars/4 heuristic, no
`tiktoken`) — nothing to scaffold.

- [X] T001 Run `make test-core` from repo root to confirm the current `core/ze-core`
  suite (including `tests/orchestration/nodes/test_memory.py`,
  `nodes/test_loop_surfacing.py`) passes cleanly before editing `memory.py`/`context.py`

**Checkpoint**: Environment ready; no code changes yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `AgentState` and `MessageTrace` field extensions both `write_memory`
(US1) and `fetch_context` (US2) write to, and `record_trace` (read by US3) depends on.
Nothing in US1/US2 can be verified end-to-end via the trace surface (US3's job) until
these land, and both nodes' return dicts reference these fields, so they must exist
first even though the fields stay `None`/`False` until US1/US2 populate them for real.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Add `compaction_span: tuple[int, int] | None` and
  `resume_recap_applied: bool` fields to `AgentState` in
  `core/ze-core/ze_core/orchestration/state.py` (data-model.md "AgentState extensions")
- [X] T003 [P] Add `CompactionTrace` dataclass (`span_start: int`, `span_end: int`) and
  extend `MessageTrace` with `compaction: CompactionTrace | None = None` and
  `resume_recap_applied: bool = False` in
  `core/ze-core/ze_core/conversation/messages/types.py` — both new fields must default
  so existing serialized traces deserialize unchanged (data-model.md "MessageTrace
  extension", contracts/trace-schema.md)
- [X] T004 Update `record_trace`
  (`core/ze-core/ze_core/orchestration/nodes/trace.py:18`) to read
  `state.get("compaction_span")` and `state.get("resume_recap_applied")`, populating
  `MessageTrace.compaction` (as `CompactionTrace(span_start=0, span_end=compaction_span[1])`
  when `compaction_span` is not `None`, else `None`) and `MessageTrace.resume_recap_applied`
  (defaulting to `False`) — mirrors how this node already reads `memory_context` for
  `memory_chunks` (depends on T002, T003)
- [X] T005 Unit test in `core/ze-core/tests/orchestration/nodes/test_trace_memory_chunks.py`
  (or a sibling file if that one is scoped too narrowly by name — check its current
  content first) covering `record_trace`'s new field population: `compaction_span=None`
  → `trace.compaction is None`; `compaction_span=(0, 7)` → `trace.compaction ==
  CompactionTrace(span_start=0, span_end=7)`; `resume_recap_applied` passthrough in both
  directions (depends on T004)

**Checkpoint**: `AgentState`/`MessageTrace` carry the new fields end-to-end through
`record_trace`, tested with both fields absent (defaults). User story implementation
can now begin.

---

## Phase 3: User Story 1 - Long conversations never break (Priority: P1) 🎯 MVP

**Goal**: Replace `write_memory`'s blind `updated[-SESSION_HISTORY_LIMIT:]` trim with a
token-budget check: only compact (summarize the older span) when the pre-slice message
list crosses 70% of the routed model's context window; otherwise send the full history
unchanged, which already fixes today's premature 5-turn cliff even before the summary
path ever triggers.

**Independent Test**: Drive a single thread through enough turns to exceed 70% of the
routed model's context window (per quickstart.md Scenario 1), plant a fact early, ask
about it after compaction has occurred, and confirm the reply is correct and the turn
completes without error — verified via `eval/run.py` and by inspecting
`compaction_span` on the triggering turn's trace.

### Tests for User Story 1

- [X] T006 [P] [US1] Unit tests for `get_context_window` in
  `core/ze-core/tests/orchestration/nodes/test_context_windows.py` — a model present in
  `MODEL_CONTEXT_WINDOWS` returns its table value; a model absent from the table returns
  `DEFAULT_CONTEXT_WINDOW_TOKENS` (FR-005 edge case)
- [X] T007 [US1] Unit tests added to `core/ze-core/tests/orchestration/nodes/test_memory.py`
  for `write_memory`'s compaction branch (`AsyncMock` for
  `config["configurable"]["openrouter_client"]`, no real DB/LLM per constitution
  Principle V): (a) under-70%-budget history → `messages` returned unchanged as
  `updated[-SESSION_HISTORY_LIMIT:]`, `compaction_span` is `None` (regression-guards
  today's existing behavior); (b) over-70%-budget history → summarization call invoked,
  returned `messages` is `[summary_message] + updated[-SESSION_HISTORY_LIMIT:]`, verbatim
  tail content is byte-identical to the pre-compaction tail, `compaction_span` is
  `(0, N-1)`; (c) repeated compaction on an already-compacted thread compacts again
  without error (FR-004); (d) summarization call raises/times out → falls back to
  `updated[-SESSION_HISTORY_LIMIT:]` with `compaction_span=None`, turn does not raise
  (FR-010, research.md R7)

### Implementation for User Story 1

- [X] T008 [P] [US1] Create `core/ze-core/ze_core/openrouter/context_windows.py` —
  `MODEL_CONTEXT_WINDOWS: dict[str, int]` seeded from the model slugs currently assigned
  in `apps/ze-api/config/config.yaml`, `DEFAULT_CONTEXT_WINDOW_TOKENS` conservative
  fallback constant, `get_context_window(model: str) -> int` accessor (research.md R3);
  module-level constant only, no mutable global (constitution "Additional Constraints")
- [X] T009 [US1] In `core/ze-core/ze_core/orchestration/nodes/memory.py`, before the
  existing `return {"messages": updated[-SESSION_HISTORY_LIMIT:]}` (line 116): add a
  chars/4 token-count estimate of `updated` (research.md R4), resolve the routed model
  via `ctx.model or resolve_model("synthesis", MODEL_SYNTHESIS, app_config)` (mirrors
  the existing call at line 130), look up `get_context_window(model)` from T008, and
  branch on the 70% threshold (FR-001) — under budget: unchanged return; at/over
  budget: split `updated` at `-SESSION_HISTORY_LIMIT`, return `compaction_span=(0,
  len(older_span)-1)` in the partial state alongside the (possibly summarized)
  `messages` (contracts/graph-nodes.md "write_memory — compaction branch")
- [X] T010 [US1] Add a new compaction-specific prompt constant (e.g. `_COMPACTION_SYSTEM`
  in `memory.py`, following the inline-module-constant pattern
  `SessionSummariser._SUMMARY_SYSTEM` uses) instructing the LLM to preserve decisions,
  constraints, outstanding tasks, and outcomes of prior actions — not a narrative topic
  recap (FR-003); wire it into the summarization call added in T009, wrapped in a
  try/except that falls back to the pre-existing trim on any error (FR-010, research.md
  R7) — depends on T009
- [X] T011 [US1] Add an eval scenario under `eval/scenarios/` scripting a long single
  thread with an early planted fact/decision and enough filler turns to force
  compaction, then a recall question — for SC-002's 90%-correct-recall target
  (quickstart.md Scenario 1); follow the existing `eval/scenarios/` YAML conventions

**Checkpoint**: A thread of arbitrary length no longer silently loses everything before
the last 5 turns, and compacts (rather than errors) once it approaches the routed
model's real context limit. This alone is a deployable MVP — SC-001/SC-002/SC-005 are
verifiable without US2/US3.

---

## Phase 4: User Story 2 - Picking a conversation back up (Priority: P2)

**Goal**: Replace `fetch_context`'s "blank history to `[]`" side effect on a long gap
with an additional, silent resume recap assembled from existing tracked state (session
narrative, open loops, in-flight goals/workflows) and injected only into the system
prompt — never a visible chat message.

**Independent Test**: Create at least one outstanding open loop/goal/workflow, let a
thread go idle past `session_inactivity_minutes`, send an unrelated new message, and
confirm the reply reflects the outstanding item with no separate "welcome back" frame,
verified via that turn's `resume_recap_applied: true` trace field (quickstart.md
Scenario 2).

### Tests for User Story 2

- [X] T012 [P] [US2] Unit tests added to a new
  `core/ze-core/tests/orchestration/nodes/test_context.py` (no test file for
  `fetch_context` exists today) for the pre-existing gap-check branch, as a regression
  baseline before adding the recap: gap under threshold → `history` unchanged from
  `state["messages"]`, no recap; gap over threshold, `AsyncMock` deps returning no
  outstanding state → `history == []` (unchanged from today), `resume_recap_applied ==
  False`, `agent_context.resume_recap is None` (FR-008)
- [X] T013 [US2] Unit tests added to the same `test_context.py` for the new recap-assembly
  path (`AsyncMock` for `get_session_summary`, `LoopSurfacer.inline_candidates`, goal/workflow
  store listings — no real DB): gap over threshold with a session summary, an open loop,
  an in-flight goal, and an in-flight workflow all present → `agent_context.resume_recap`
  is a non-empty string containing content derived from all four sources,
  `resume_recap_applied == True`; gap under threshold with the same outstanding state
  present → recap still `None` (FR-009, session-boundary-only) (depends on T012)

### Implementation for User Story 2

- [X] T014 [P] [US2] Add `resume_recap: str | None = None` field to `AgentContext` in
  `core/ze-agents/ze_agents/types.py`, following the existing `screen_context_note`
  field's doc-comment convention (runtime-only if applicable — confirm against
  checkpoint-serde constraints already documented on neighboring fields)
- [X] T015 [US2] In `core/ze-core/ze_core/orchestration/nodes/context.py`, add a
  `_assemble_resume_recap(state, config) -> ResumeRecap | None` helper: reads
  `config["configurable"]` handles for session-summary retrieval
  (`get_session_summary(session_id)`), `LoopSurfacer.inline_candidates` (seeded via the
  same `_extract_seeds`-style entity extraction `nodes/loop_surfacing.py` already uses),
  and active goal/workflow listings (no thread filter — single-user, research.md R5);
  returns `None` when nothing is outstanding (FR-008) (depends on T014)
- [X] T016 [US2] Define `ResumeRecap` as a dataclass (fields: `session_narrative`,
  `open_loop_lines`, `in_flight_goal_lines`, `in_flight_workflow_lines`, `gap_minutes`
  per data-model.md) with a `render() -> str` method producing the text block injected
  into `agent_context.resume_recap`; place it alongside `_assemble_resume_recap` in
  `context.py` or a small sibling module if `context.py` gets too large — the seam is
  local to this node, no cross-package type needed (depends on T015)
- [X] T017 [US2] Wire T015/T016 into `fetch_context`'s existing gap-check branch
  (`context.py:64-66`): when the gap is exceeded, call `_assemble_resume_recap`, set
  `agent_context.resume_recap = recap.render()` when `recap` is not `None` (added right
  after `agent_context` is constructed, mirroring the `screen_context_note` assignment
  at line 121), and include `resume_recap_applied` in this node's returned partial state
  dict (contracts/graph-nodes.md "fetch_context — resume-recap branch") (depends on
  T016)
- [X] T018 [US2] Extend `BaseAgent._build_system_prompt` in
  `core/ze-agents/ze_agents/base_agent.py` (~lines 162-163) to render
  `ctx.resume_recap` into the system prompt the same way `ctx.screen_context_note`
  already is, and confirm it is never appended to `ctx.messages`/`state["messages"]`
  anywhere in the call path (FR-007a) — depends on T014

**Checkpoint**: Both User Stories 1 AND 2 work independently; a resumed thread reflects
outstanding state without a visible banner, and long threads still compact correctly.

---

## Phase 5: User Story 3 - Trusting what was kept vs. summarized (Priority: P3)

**Goal**: Confirm the trace fields wired in Phase 2 (Foundational) and populated by US1
(`compaction_span`) and US2 (`resume_recap_applied`) are actually inspectable end-to-end
through the existing `GET /api/v0/messages/{id}/trace` payload shape
(contracts/trace-schema.md) — this phase is validation-only; no new production field is
introduced here, T002-T005 already did that work because both US1 and US2 depend on it.

**Independent Test**: Trigger compaction (US1's independent test), then call
`GET /api/v0/messages/{id}/trace` for that turn's message id and confirm the response
includes `compaction: {span_start, span_end}` matching the span that was actually
folded (quickstart.md Scenario 3).

### Tests for User Story 3

- [X] T019 [US3] Integration-style test (still `AsyncMock`, no real DB) confirming
  the full path from a `write_memory` compaction return through `record_trace` to a
  serialized `MessageTrace.compaction` payload matches contracts/trace-schema.md's
  "After" shape exactly (field names, `null`-when-absent behavior) — place in
  `core/ze-core/tests/orchestration/nodes/test_trace_memory_chunks.py` alongside T005 or
  a clearly-named sibling if that file's scope doesn't fit
- [X] T020 [US3] Same coverage for `resume_recap_applied` (sequential with T019 — same
  test file, not run in parallel): a turn where
  `fetch_context` set `resume_recap_applied=True` produces
  `MessageTrace.resume_recap_applied == True` in the serialized trace; a turn where it
  never ran (short gap) produces `False`, not `None`/missing (data-model.md "MessageTrace
  extension")

### Implementation for User Story 3

- [X] T021 [US3] Run quickstart.md Scenario 3 manually against `make dev` (or the eval
  harness) once T007/T013/T019/T020 are green, to confirm the REST payload — not just
  the in-process dataclass — actually carries the new fields through
  `MessageStore.save_trace`/the existing trace route with no serialization gap
  (`zc020_message_trace.py`'s JSONB column, no migration needed)

**Checkpoint**: All three user stories independently functional; compaction and resume
recap are both inspectable via the existing trace surface, satisfying FR-011.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the full spec end-to-end and close remaining edge cases not tied
to a single user story.

- [X] T022A [P] Integration test for FR-012 (compaction and resume recap must compose
  on the same turn without either discarding the other — spec.md Edge Cases, "What
  happens when compaction and a resume brief would both apply to the same turn"):
  construct a state/config fixture where both conditions are true simultaneously — a
  gap since `last_active_at` exceeding `session_inactivity_minutes` (triggers
  `fetch_context`'s resume-recap branch) AND a message history over 70% of the routed
  model's context window (triggers `write_memory`'s compaction branch) — and assert
  that the same turn ends with `agent_context.resume_recap` non-`None` (or
  `resume_recap_applied=True`) AND `compaction_span` non-`None`, i.e. neither node's
  output is lost or overwritten by the other. Place in
  `core/ze-core/tests/orchestration/test_edges.py` (existing file covering
  cross-node graph behavior) or a new
  `core/ze-core/tests/orchestration/test_context_continuity_composition.py` if
  `test_edges.py`'s scope doesn't fit
- [X] T022 [P] Run quickstart.md Scenario 4 (compaction LLM-call failure fallback,
  FR-010) manually or via a targeted integration test forcing
  `config["configurable"]["openrouter_client"].complete` to raise, confirming the turn
  still completes (covered at the unit level by T007d; this closes the loop
  end-to-end)
- [X] T023 [P] Run quickstart.md Scenario 5 (unknown-model fallback, FR-005/SC-005)
  end-to-end against a model deliberately absent from `MODEL_CONTEXT_WINDOWS`
- [X] T024 Update `specs/README.md`'s phase index row for Phase 112 and flip this
  spec's `Status` field from `Draft` to `Implemented` in the same commit as the
  implementation (constitution Principle I)
- [X] T025 Run `make test-core` and `make lint` from repo root; both must pass before
  this phase is considered done (constitution Principle V)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
  (T004/`record_trace` references fields both US1 and US2 write to)
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1 and US2 touch different nodes (`memory.py` vs `context.py`) and different new
    modules (`openrouter/context_windows.py` vs `ze_agents/types.py`) — genuinely
    independent, can proceed in parallel
  - US3 is validation-only and depends on both US1 (for `compaction_span` to have a
    real, non-`None` case to assert on) and US2 (same for `resume_recap_applied`) having
    landed — sequence US3 after US1+US2, not in parallel with them
- **Polish (Phase 6)**: Depends on US1+US2+US3 all being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational — no dependency on US2
- **User Story 2 (P2)**: Can start after Foundational — no dependency on US1 (different
  node, different file)
- **User Story 3 (P3)**: Depends on US1 AND US2 (validates fields both populate) — not
  independently startable before them, despite the template's usual "independent"
  framing; this is a deliberate deviation because US3's entire value proposition is
  inspecting output US1/US2 produce

### Within Each User Story

- Tests written and expected to fail before implementation (T006-T007 before
  T008-T011; T012-T013 before T014-T018)
- New types/modules before the node logic that uses them (T008 before T009; T014
  before T015)
- Node logic before prompt-rendering wiring (T015-T016 before T017; T017 before T018)

### Parallel Opportunities

- T002 and T003 (Foundational) — different files
- T006 (US1) can run parallel to T007 once both are test-writing (different files)
- T008 (US1, `context_windows.py`) can run parallel to T012-T014 (US2, `context.py`/`types.py`)
  once Foundational is done — genuinely different files, no shared state
- T019 and T020 (US3) — same file, kept sequential (not marked `[P]`) per this note
- T022, T022A, and T023 (Polish) — independent scenarios/files, safe to parallelize

---

## Parallel Example: Foundational + User Story 1 kickoff

```bash
# Once Setup (T001) is done, launch Foundational together:
Task: "Add compaction_span/resume_recap_applied to AgentState in state.py"
Task: "Add CompactionTrace/MessageTrace fields in conversation/messages/types.py"

# After Foundational (T002-T005) lands, User Story 1 and User Story 2 can start
# in parallel by different developers/agents:
Task: "US1 — get_context_window tests + context_windows.py"
Task: "US2 — fetch_context gap-check regression tests + AgentContext.resume_recap"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: quickstart.md Scenario 1 — long thread, planted fact, compaction
   triggers, recall still correct
5. Deploy/demo if ready — SC-001, SC-002, SC-004, SC-005 are all verifiable at this
   point without US2/US3

### Incremental Delivery

1. Complete Setup + Foundational → foundation ready
2. Add User Story 1 → validate independently → deploy/demo (MVP — fixes the reliability
   floor)
3. Add User Story 2 → validate independently → deploy/demo (resume recap, SC-003)
4. Add User Story 3 → validate against US1+US2's already-shipped output (trace
   transparency, no new production behavior)
5. Polish → close remaining edge cases (T022-T023), update spec status (T024)

### Parallel Team Strategy

With two developers: after Foundational, one takes US1 (`memory.py`/`context_windows.py`),
the other takes US2 (`context.py`/`ze_agents` `types.py`/`base_agent.py`) — genuinely
disjoint files, no merge conflicts expected. US3 waits for both to land before starting.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- No new graph nodes — every task edits an existing node (`write_memory`,
  `fetch_context`, `record_trace`) or adds a small new module those nodes import
  (research.md R1's corrected finding)
- Verify tests fail before implementing (T006-T007, T012-T013 first)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: reintroducing a second inactivity-threshold constant (FR-006 explicitly
  forbids it — reuse `session_inactivity_minutes` as read today), reintroducing new
  graph nodes for either mechanism
