# Feature Specification: AgentContext Derivation

**Feature Branch**: `200-agent-context-derivation`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 198

**Input**: Architecture review 2026-10-22, candidate C3. One owner for deriving an `AgentContext` (`for_subtask`, `for_delegate`, `for_unattended`). Conductor and procedure state return in one value. `AgentState` fields declare whether they are turn-scoped or thread-scoped, and the per-turn reset is generated from those declarations. A table test covers every field.

## Context

This is a deepening refactor. Its users are the maintainers of the turn engine, and the guarantees it protects are ones the user sees: the time in a reply, the screen they were looking at, the reply that a workflow links to, and a trace that describes the right turn.

Today the derivation of a child context from the turn context has no owner. Each construction site copies whichever fields its author thought of. The sites checked on 2026-10-22:

| Site | What it copies | What it drops (examples) |
|---|---|---|
| `ze_core/orchestration/nodes/execution.py:388` (`_execute_single`) | 22 named fields plus four `**_*_kwargs` helpers | `timezone`, `extensions` (so `user_message_id` is lost), `memory_store`, `sources` |
| `nodes/execution.py:493` (`_execute_compound`) | the same list, written out a second time (line 507 is misindented) | the same |
| `ze_agents/delegate.py:270` (specialist delegate) | 19 named fields | `timezone`, `embed_fn`, `token_sink`, `screen_context_note`, `preset_note`, `resume_recap`, `active_skills`. Some of these drops may be deliberate; the code does not say which |
| `ze_automation/goals/executor.py:906` (goal milestone) | 5 fields plus the resume kwargs | `timezone`, `tool_sink`, `abort_token`, `reporter` |
| `ze_agents/base_agent.py:355` (`run_undo`), `apps/ze-api/ze_api/api/ws/ui_actions.py:152` (screen action) | `session_id` and an empty prompt | everything, by design |

Consequences that a user sees:
- **Wrong time.** `fetch_context` sets `timezone` (`nodes/context.py:345`), but neither execution path copies it. Every routed agent's "Current date and time" line (`base_agent.py:251`) is therefore in UTC. Phase 198 patches the two sites; this phase removes the class of bug.
- **Lost reply link.** `fetch_context` puts `user_message_id` in `extensions` (`nodes/context.py:371`). The workflow agent reads it (`ze_automation/agents/workflow/agent.py:108`), but routed runs drop `extensions`, so the workflow it creates may not link back to the user's message.

Conductor and procedure state are worse: they live in three places. `AgentState`, the base context and the child context each hold a copy. After the run they are copied back by hand (`execution.py:415-454`, `_sync_procedure_invocation` at `:366`), with `getattr` guards on fields that always exist.

The per-turn reset (`make_graph_input`, `ze_core/conversation/turn.py:32-90`) must mirror `AgentState` (`ze_core/orchestration/state.py`) by hand. Six fields are missing from it: `compaction_span`, `resume_recap_applied`, `open_items_query`, `loop_offer_ids`, `pre_approved_writes` and `procedure_matches`. Comments such as "set by fetch_context every turn" are the only thing standing in for the missing reset. The missing `compaction_span` reset is part of bug B6 (compaction shown one turn late). Phase 198 fixes B6; this phase makes the reset complete by construction.

**Blast radius** (`graphify affected AgentContext --depth 1`, 2026-10-22):
- Source references: ze-agents 41, ze-core 20, ze-automation 8, ze-personal 7, ze-calendar 6, ze-news 4, ze-prospecting 3, ze-messenger 3, ze-finance 3, ze-worldstate 3, ze-priority 3, ze-memory 2, ze-ingestion 2, ze-api 2, ze-sdk 1.
- Test references: about 200.
- Almost all of these only type a `ctx` parameter. Only the seven construction sites above build contexts, and this phase changes only those.
- `AgentState` has 48 source references, all in ze-core.
- `make_graph_input` callers: `invoke_raw_turn`, `make_graph_input_from_raw_text`, core `Container.invoke`, ze-api `wiring/workflow_graph.py:18`, `ze_automation/bootstrap.py:246`, and 7 test modules.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every agent run sees the turn it belongs to (Priority: P1)

A maintainer adds a field to the turn context, such as a new prompt note. Every agent that runs in that turn sees it: a single specialist, a compound subtask, a delegate, or a goal milestone. If a kind of run should not inherit the field, the maintainer says so once, where derivation is defined, not at each site.

**Why this priority**: The missing timezone and the dropped `user_message_id` are user-visible bugs that came straight from hand copies. Every new context field (phases 187b, 195, 197) has had to be added at three or more sites.

**Independent Test**: For each kind of derivation, a table test asserts that every `AgentContext` field is either inherited or deliberately reset, with the reason. The test fails when a field is added without a choice.

**Acceptance Scenarios**:

1. **Given** the user's timezone is Europe/Lisbon, **When** a turn routes to a single specialist, a compound subtask or a delegate, **Then** each agent's prompt shows Lisbon time.
2. **Given** a turn whose user message has an id, **When** the workflow agent runs as a routed specialist, **Then** it can read that id.
3. **Given** a maintainer adds a new field to `AgentContext` and declares no inheritance, **When** the test suite runs, **Then** the derivation table test fails and names the field.
4. **Given** a delegate run, **When** it is derived, **Then** what it does not inherit from its caller (for example the token sink, so the specialist's tokens are not streamed as the companion's reply) is listed in one place with the reason.

---

### User Story 2 - Conductor and procedure state come back in one value (Priority: P2)

After a subtask or delegate runs, the conductor ledger, delegate counts and procedure invocation it produced reach the turn state through one return value. Nothing copies fields back by hand, and nothing has to guess which copy is current.

**Why this priority**: Three copies of the same state is where the trace's conductor section (`nodes/trace.py:332-337`) and the procedure ledger can disagree. It is the second-largest source of `getattr` guards in the engine.

**Independent Test**: A compound turn whose subtasks each delegate once ends with a conductor ledger and delegate total equal to the sum over subtasks, read from `AgentState` alone. This holds both when a subtask pauses for a confirmation and resumes, and when it does not.

**Acceptance Scenarios**:

1. **Given** a single-specialist turn in which the companion delegates twice, **When** the turn ends, **Then** `AgentState` and the trace both show two delegates, and no code path copies `conductor_*` fields between contexts.
2. **Given** a subtask that invoked a procedure, **When** the turn ends, **Then** the procedure invocation recorded for the turn is that subtask's invocation.
3. **Given** a subtask that paused for a write confirmation, **When** the turn resumes, **Then** the conductor state from before the pause is preserved exactly once.

---

### User Story 3 - The per-turn reset is complete by construction (Priority: P2)

Each `AgentState` field, including the fields of plugin state extensions, declares whether it lives for one turn or for the whole thread. The graph input that starts a turn resets every turn-scoped field. A maintainer never edits a separate reset list.

**Why this priority**: Six fields are missing from today's hand-kept list. B6 shows what that costs: the trace reports compaction one turn late.

**Independent Test**: A test enumerates every `AgentState` key, plus the keys of every registered state extension. It asserts that each key is declared turn-scoped or thread-scoped, and that the graph input sets every turn-scoped key to its declared reset value and omits every thread-scoped key.

**Acceptance Scenarios**:

1. **Given** a turn that set `loop_offer_ids`, **When** the next turn starts, **Then** `loop_offer_ids` starts empty.
2. **Given** `messages` and `last_active_at` are thread-scoped, **When** a turn starts, **Then** they keep their checkpointed values (today's behaviour, `turn.py:41-44`).
3. **Given** a plugin state extension field with no lifetime declared, **When** the graph is built, **Then** startup fails with an error that names the field.

---

### Edge Cases

- **Image turns.** A turn with an image builds a different first message (`_build_messages`). The derivation keeps that per-subtask choice.
- **Resumed subtasks.** On resume, the resume kwargs (`_resume_kwargs`: `resume`, `write_decisions`, `approval_request_id`, `write_round`) differ per subtask index. They are inputs to the derivation, not fields it inherits.
- **Retry runs.** `retry_mode` must reach every derived context, including delegates, because the write gates read it.
- **Delegate depth.** A delegate's `extensions` carries `_delegate_depth`. The derivation must merge it with the inherited extensions, not replace them, or `user_message_id` is lost again.
- **Undo and screen actions.** `run_undo` and the screen action run with no turn context. They stay a separate, explicitly minimal construction, also covered by the table test.
- **Goal milestones** run unattended with no turn. `for_unattended` lists what an unattended run gets: the timezone from settings, `memory_store`, `pre_approved_writes` and the goal id. It does not get prompt notes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The engine MUST have one owner for deriving a child `AgentContext`, with one operation per kind of run: subtask, delegate, unattended. Child contexts MUST NOT be built field by field anywhere else.
- **FR-002**: Each `AgentContext` field MUST declare, per kind of derivation, whether it is inherited or reset. A field with no declaration MUST fail a test.
- **FR-003**: A routed agent, compound subtask, delegate and goal milestone MUST receive the user's timezone.
- **FR-004**: A derived context MUST keep the parent's `extensions` (including `user_message_id`), merged with any keys that kind of derivation adds, such as `_delegate_depth`.
- **FR-005**: Conductor state (hint, ledger, per-agent delegate counts, total) and procedure invocation state MUST flow from a child run back to the turn through one returned value. Code that copies these fields back from a child context MUST be deleted.
- **FR-006**: Each `AgentState` field MUST declare its lifetime (turn or thread) and its reset value where it lives. The graph input for a new turn MUST be generated from those declarations.
- **FR-007**: Plugin state extensions MUST declare field lifetimes the same way. Building the graph MUST fail when an extension field has none.
- **FR-008**: `compaction_span`, `resume_recap_applied`, `open_items_query`, `loop_offer_ids`, `pre_approved_writes` and `procedure_matches` MUST each be declared, so the generated reset covers them, or they are thread-scoped with a recorded reason.
- **FR-009**: The `getattr(..., default)` guards on `AgentContext` fields in `nodes/execution.py` and `nodes/trace.py` that exist only because the fields might be missing MUST be removed, because the type guarantees the fields.
- **FR-010**: Behaviour MUST NOT change otherwise. The existing turn, conductor, write-confirmation, retry and workflow test suites MUST pass unchanged, apart from tests that asserted the old hand copies.

### Key Entities

- **Turn context**: the `AgentContext` that `fetch_context` builds for one turn. Every other context in the turn is derived from it.
- **Derivation**: one named way to make a child context: subtask, delegate or unattended. Each declares what it inherits and what it resets.
- **Child run outcome**: what a child run hands back besides its `AgentResult`: the conductor ledger delta, delegate counts and procedure invocation.
- **Field lifetime**: whether an `AgentState` field is turn-scoped (reset at each turn) or thread-scoped (kept across turns).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No file outside the derivation owner builds an `AgentContext` from another `AgentContext`. A grep for `AgentContext(` finds the turn context in `fetch_context`, the derivation owner, and the two minimal constructions (undo and screen action).
- **SC-002**: The derivation table test covers every `AgentContext` field for every derivation kind: 100% of fields declared.
- **SC-003**: The reset test covers every `AgentState` and state-extension key: 0 undeclared keys.
- **SC-004**: Adding a new `AgentContext` field requires editing exactly one place for inheritance, down from three to six today.
- **SC-005**: A routed reply shows the user's local time in every routing path (single, compound, delegate, milestone), each verified by a test.

## Assumptions

- Phase 198 has already patched the timezone sites (B1) and the compaction reset (B6). This phase replaces those patches with the general mechanism and keeps their regression tests.
- `AgentContext` keeps its name and stays one type. The roughly 300 references that only type a `ctx` parameter do not change. Splitting the type into runtime handles, turn content and write-gate state is out of scope; phase 209 (the write gate) may revisit it.
- The delegate's current drops of `token_sink`, `active_skills` and the prompt notes are assumed deliberate: a specialist must not stream into the companion's reply or inherit the companion's skill narrowing. They are recorded as resets with that reason. Any found to be accidental are listed for the user during planning.
- The typed turn services of phase 201 come later. In this phase the derivation still reads `tool_sink` and `script_runner` from `config["configurable"]` where it does today.
- Out of scope: the trace recorder (phase 208), which consumes the single child-run outcome defined here; and the workflow graph's own state extension, beyond declaring its lifetimes.
