# Feature Specification: AgentContext Derivation

**Feature Branch**: `200-agent-context-derivation`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 198

**Governed by**: phase 151 (fat delegate), phase 153 (conductor ledger and delegate caps), phase 139 (procedure activation), phase 181 (write confirmation state on the context), phase 165 (Retry), `specs/arch/langgraph-orchestration.md` (graph state is checkpointed; runtime handles never are), `specs/arch/pre-v1-hard-cuts.md`, `specs/GLOSSARY.md` (Turn, Thread).

**Doctrine functions served**: action (every agent run in a turn acts with the turn's facts: the user's time, the message it answers), governance (what a child run may not inherit, such as the reply stream or the skill narrowing, is decided in one place).

**Owning packages** (for planning): ze-agents (`types.py`, `delegate.py`, `base_agent.py` undo construction), ze-core (`orchestration/nodes/execution.py`, `nodes/context.py`, `orchestration/state.py`, `conversation/turn.py`), ze-automation (`goals/executor.py`), ze-personal (`graph/workflow.py` state extension and per-step reset), ze-api (`api/ws/ui_actions.py`, `wiring/workflow_graph.py`). No migration, no REST or WS change.

**Input**: Architecture review 2026-10-22, candidate C3. One owner for deriving an `AgentContext` (`for_subtask`, `for_delegate`, `for_unattended`). Conductor and procedure state return in one value. `AgentState` fields declare whether they are turn-scoped or thread-scoped, and the per-turn reset is generated from those declarations. A table test covers every field.

## Context

This is a deepening refactor. Its users are the maintainers of the turn engine, and the guarantees it protects are ones the user sees: the time in a reply, the screen they were looking at, the reply that a workflow links to, and a trace that describes the right turn.

Today the derivation of a child context from the turn context has no owner. Each construction site copies whichever fields its author thought of. The sites checked on 2026-10-22:

| Site | What it copies | What it drops (examples) |
|---|---|---|
| `ze_core/orchestration/nodes/execution.py:388` (`_execute_single`) | 18 named fields, plus four `**_*_kwargs` helpers that spread 16 more | `timezone`, `extensions` (so `user_message_id` is lost), `memory_store`, `sources` |
| `nodes/execution.py:493` (`_execute_compound`) | the same list, written out a second time (line 507 is misindented) | the same |
| `ze_agents/delegate.py:270` (specialist delegate) | 19 named fields | `timezone`, `embed_fn`, `token_sink`, `screen_context_note`, `preset_note`, `resume_recap`, `open_priorities_note`, `active_skills`, `skill_tool_names`, the procedure fields (including the `procedure_tool_names` narrowing) and the conductor fields. It also *replaces* `extensions` with `{"_delegate_depth": …}`, so `user_message_id` is lost. Some of these drops may be deliberate; the code does not say which |
| `ze_automation/goals/executor.py:906` (goal milestone) | 5 fields plus the resume kwargs | `timezone`, `tool_sink`, `abort_token`, `reporter` |
| `ze_agents/base_agent.py:355` (`run_undo`), `apps/ze-api/ze_api/api/ws/ui_actions.py:152` (screen action) | `session_id` and an empty prompt | everything, by design |

Consequences that a user sees:
- **Wrong time.** `fetch_context` sets `timezone` (`nodes/context.py:345`), but neither execution path copies it. Every routed agent's "Current date and time" line (`base_agent.py:251`) is therefore in UTC. Phase 198 patches the two sites; this phase removes the class of bug.
- **Lost reply link.** `fetch_context` puts `user_message_id` in `extensions` (`nodes/context.py:371`). The workflow agent reads it (`ze_automation/agents/workflow/agent.py:108`), but routed runs drop `extensions`, so the workflow it creates may not link back to the user's message.

Conductor and procedure state are worse: they live in three places. `AgentState`, the base context and the child context each hold a copy. After a single-specialist run they are copied back by hand (`execution.py:415-454`, `_sync_procedure_invocation` at `:366`), with `getattr` guards on fields that always exist (`AgentContext` declares every one of them, `ze_agents/types.py:161-174`).

The compound path does not copy them back at all. `_execute_compound` (`execution.py:536-543`) returns the base context unchanged: no conductor ledger, no delegate total, no procedure invocation, and no `record_guided_actions`. Its subtasks also share some of that state by accident. `_conductor_kwargs` hands every subtask the *same* `conductor_delegate_counts` dict (`execution.py:29-40`), so the per-specialist delegate cap counts across subtasks. But `conductor_delegate_total` is an integer copied per subtask, so the per-turn cap (`delegate.py:151-158`) applies per subtask. And `conductor_ledger` is `base.ledger or []`, so an empty ledger becomes a fresh list per subtask and is dropped. Today only the companion delegates, so this matters only when the companion is one subtask of a compound turn.

The per-turn reset (`make_graph_input`, `ze_core/conversation/turn.py:32-90`) must mirror `AgentState` (`ze_core/orchestration/state.py`) by hand. Six fields are missing from it: `compaction_span`, `resume_recap_applied`, `open_items_query`, `loop_offer_ids`, `pre_approved_writes` and `procedure_matches`. Comments such as "set by fetch_context every turn" are the only thing standing in for the missing reset. The missing `compaction_span` reset is part of bug B6 (compaction shown one turn late). Phase 198 fixes B6; this phase makes the reset complete by construction.

**Blast radius** (`graphify affected AgentContext --depth 1`, 2026-10-22):
- Source references: ze-agents 41, ze-core 20, ze-automation 8, ze-personal 7, ze-calendar 6, ze-news 4, ze-prospecting 3, ze-messenger 3, ze-finance 3, ze-worldstate 3, ze-priority 3, ze-memory 2, ze-ingestion 2, ze-api 2, ze-sdk 1.
- Test references: about 200.
- Almost all of these only type a `ctx` parameter. Only the seven construction sites above build contexts, and this phase changes only those.
- `AgentState` has 48 source references, all in ze-core.
- `make_graph_input` callers: `invoke_raw_turn`, `make_graph_input_from_raw_text`, core `Container.invoke`, ze-api `begin_workflow_turn` (`wiring/workflow_graph.py:18`), and 7 test modules. (The review listed `ze_automation/bootstrap.py:246` as a caller. It is not: `bootstrap.py:287` takes `begin_workflow_turn`'s output and adds the workflow keys by hand.)
- **A third reset list.** The workflow graph resets state between steps in `load_workflow_step` (`ze_personal/graph/workflow.py:98-121`). It resets 16 engine keys by hand (plus its own workflow keys) and leaves the rest, such as `judgments`, `components`, the conductor fields, `tier` and `skill_matches`, to carry from one step into the next.

## Clarifications

### Session 2026-10-22

- Q: Does phase 200 group the write-gate fields of `AgentContext` into one part, for phase 209's write gate to read? → A: Yes. Phase 200 groups `resume`, `write_decisions`, `pre_approved_writes`, `write_round`, `approval_request_id`, `loop_active` and `retry_mode` into one write-gate part of the context, and the derivation treats that part as one unit (FR-011).
- Q: What does a delegate inherit from its caller? → A: The timezone, `extensions` (merged, so `user_message_id` survives), `embed_fn` and `memory_store`. It resets the token sink, the prompt notes, the skill and procedure narrowing and the procedure state, each recorded with its reason (FR-012).
- Q: In a compound turn, does the subtasks' conductor state merge? → A: Yes. Ledgers concatenate, per-agent counts and totals sum, and the delegate caps apply per turn across subtasks. This is a deliberate behaviour change (FR-013).
- Q: How do workflow steps reset state? → A: Each workflow step counts as a turn: the generated turn reset runs at every step, and the workflow fields are scoped to the run. `load_workflow_step`'s hand-written list is deleted (FR-014).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every agent run sees the turn it belongs to (Priority: P1)

A maintainer adds a field to the turn context, such as a new prompt note. Every agent that runs in that turn sees it: a single specialist, a compound subtask, a delegate, or a goal milestone. If a kind of run should not inherit the field, the maintainer says so once, where derivation is defined, not at each site.

**Why this priority**: The missing timezone and the dropped `user_message_id` are user-visible bugs that came straight from hand copies. Every new context field (phases 187b, 195, 197) has had to be added at three or more sites.

**Independent Test**: For each kind of derivation, a table test asserts that every `AgentContext` field is either inherited or deliberately reset, with the reason. The test fails when a field is added without a choice.

**Acceptance Scenarios**:

1. **Given** the user's timezone is Europe/Lisbon, **When** a turn routes to a single specialist, a compound subtask or a delegate, **Then** each agent's prompt shows Lisbon time.
2. **Given** a turn whose user message has an id, **When** the workflow agent runs as a routed specialist, **Then** it can read that id.
3. **Given** a maintainer adds a new field to `AgentContext` and declares no inheritance, **When** the test suite runs, **Then** the derivation table test fails and names the field.
4. **Given** a delegate run, **When** it is derived, **Then** it inherits the caller's timezone, `extensions`, `embed_fn` and `memory_store`, and what it does not inherit (the token sink, so the specialist's tokens are not streamed as the companion's reply; the prompt notes; the skill and procedure narrowing; the procedure state) is listed in one place with the reason.
5. **Given** the companion delegates during a turn whose user message has an id, **When** the specialist runs, **Then** it can read that id.

---

### User Story 2 - Conductor and procedure state come back in one value (Priority: P2)

After a subtask or delegate runs, the conductor ledger, delegate counts and procedure invocation it produced reach the turn state through one return value. Nothing copies fields back by hand, and nothing has to guess which copy is current.

**Why this priority**: Three copies of the same state is where the trace's conductor section (`nodes/trace.py:332-337`) and the procedure ledger can disagree. It is the second-largest source of `getattr` guards in the engine.

**Independent Test**: A compound turn whose subtasks each delegate once ends with a conductor ledger and delegate total equal to the sum over subtasks, read from `AgentState` alone. This holds both when a subtask pauses for a confirmation and resumes, and when it does not.

**Acceptance Scenarios**:

1. **Given** a single-specialist turn in which the companion delegates twice, **When** the turn ends, **Then** `AgentState` and the trace both show two delegates, and no code path copies `conductor_*` fields between contexts.
2. **Given** a subtask that invoked a procedure, **When** the turn ends, **Then** the procedure invocation recorded for the turn is that subtask's invocation.
3. **Given** a subtask that paused for a write confirmation, **When** the turn resumes, **Then** the conductor state from before the pause is preserved exactly once.
4. **Given** a compound turn whose subtasks together would pass the per-turn delegate cap, **When** they delegate, **Then** the cap stops the delegate that would pass it, whichever subtask makes it.

---

### User Story 3 - The per-turn reset is complete by construction (Priority: P2)

Each `AgentState` field, including the fields of plugin state extensions, declares whether it lives for one turn or for the whole thread. The graph input that starts a turn resets every turn-scoped field. A maintainer never edits a separate reset list.

**Why this priority**: Six fields are missing from today's hand-kept list. B6 shows what that costs: the trace reports compaction one turn late.

**Independent Test**: A test enumerates every `AgentState` key, plus the keys of every registered state extension. It asserts that each key is declared turn-scoped or thread-scoped, and that the graph input sets every turn-scoped key to its declared reset value and omits every thread-scoped key.

**Acceptance Scenarios**:

1. **Given** a turn that set `loop_offer_ids`, **When** the next turn starts, **Then** `loop_offer_ids` starts empty.
2. **Given** `messages` and `last_active_at` are thread-scoped, **When** a turn starts, **Then** they keep their checkpointed values (today's behaviour, `turn.py:41-44`).
3. **Given** a plugin state extension field with no lifetime declared, **When** the graph is built, **Then** startup fails with an error that names the field.
4. **Given** a workflow whose first step wrote judgment rows and components, **When** the second step starts, **Then** both start empty, and the workflow's own fields (steps, results, visit counts) keep their values.

---

### Edge Cases

- **Image turns.** A turn with an image builds a different first message (`_build_messages`). The derivation keeps that per-subtask choice.
- **Resumed subtasks.** On resume, the resume kwargs (`_resume_kwargs`: `resume`, `write_decisions`, `approval_request_id`, `write_round`) differ per subtask index. They are inputs to the derivation, not fields it inherits.
- **Retry runs.** `retry_mode` must reach every derived context, including delegates, because the write gates read it.
- **Delegate depth.** A delegate's `extensions` carries `_delegate_depth`. The derivation must merge it with the inherited extensions, not replace them, or `user_message_id` is lost again.
- **Undo and screen actions.** `run_undo` and the screen action run with no turn context. They stay a separate, explicitly minimal construction, also covered by the table test.
- **Workflow steps.** A workflow step is a turn for lifetime purposes. At each step the generated turn reset runs, then the step sets its own prompt and pre-approved writes. Run-scoped workflow fields (`workflow_steps`, `workflow_step_results`, `visit_counts` and the rest of the extension) are declared as such.
- **Two subtasks invoke a procedure.** Today the compound path records none. With the merge, each subtask's invocation is kept in the child-run outcome; planning decides how the turn's single procedure trace shows more than one.
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
- **FR-010**: Behaviour MUST NOT change otherwise, apart from FR-012 (a delegate now gets the timezone and `user_message_id`), FR-013 and FR-014. The existing turn, conductor, write-confirmation, retry and workflow test suites MUST pass unchanged, apart from tests that asserted the old hand copies.

- **FR-011**: The write-gate fields (`resume`, `write_decisions`, `pre_approved_writes`, `write_round`, `approval_request_id`, `loop_active`, `retry_mode`) MUST be grouped into one part of `AgentContext`. Each derivation MUST declare that part as one unit: a subtask and a delegate inherit it, with the resume inputs set per subtask, and an unattended run gets only its pre-approved writes and no Retry.
- **FR-012**: A delegate MUST inherit the caller's timezone, `extensions` (merged with `_delegate_depth`), `embed_fn` and `memory_store`. It MUST NOT inherit the token sink, the prompt notes (screen, preset, resume recap, open priorities, preset key), the skill narrowing (`active_skills`, `skill_tool_names`) or the procedure state and narrowing. Each reset MUST carry its reason in the derivation declaration.
- **FR-013**: In a compound turn, the child-run outcomes of all subtasks MUST merge into the turn: ledger entries concatenate in subtask order, per-agent delegate counts and the delegate total sum, and the per-specialist and per-turn delegate caps MUST apply across all subtasks of the turn.
- **FR-014**: The workflow graph MUST reset turn-scoped state at every step from the same declarations. `load_workflow_step` MUST NOT keep its own reset list. Workflow extension fields MUST be declared run-scoped.

### Key Entities

- **Turn context**: the `AgentContext` that `fetch_context` builds for one turn. Every other context in the turn is derived from it.
- **Derivation**: one named way to make a child context: subtask, delegate or unattended. Each declares what it inherits and what it resets.
- **Child run outcome**: what a child run hands back besides its `AgentResult`: the conductor ledger delta, delegate counts and procedure invocation.
- **Field lifetime**: whether an `AgentState` field is turn-scoped (reset at each turn, and at each workflow step) or thread-scoped (kept across turns; a workflow run's own fields are kept for the run).
- **Write-gate state**: the part of a context that the write gates read: the parked loop to resume, the user's decisions, pre-approved writes, the confirmation round and request id, whether the loop is active, and Retry mode. Phase 209's write gate reads it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No file outside the derivation owner builds an `AgentContext` from another `AgentContext`. A grep for `AgentContext(` finds the turn context in `fetch_context`, the derivation owner, and the two minimal constructions (undo and screen action).
- **SC-002**: The derivation table test covers every `AgentContext` field for every derivation kind: 100% of fields declared.
- **SC-003**: The reset test covers every `AgentState` and state-extension key: 0 undeclared keys.
- **SC-004**: Adding a new `AgentContext` field requires editing exactly one place for inheritance, down from three to six today.
- **SC-005**: A routed reply shows the user's local time in every routing path (single, compound, delegate, milestone), each verified by a test.

## Assumptions

- Phase 198 has already patched the timezone sites (B1) and the compaction reset (B6). This phase replaces those patches with the general mechanism and keeps their regression tests.
- `AgentContext` keeps its name and stays one type. The roughly 300 references that only type a `ctx` parameter do not change.
- Phase 200 groups the write-gate state (FR-011), which phase 209's write gate reads. Splitting the rest of `AgentContext` (runtime handles, turn content) stays out of scope.
- A delegate gets no prompt notes and no skill or procedure narrowing because the specialist uses its own tools, and the companion's fat brief (phase 151) carries the context it needs.
- The typed turn services of phase 201 come later. In this phase the derivation still reads `tool_sink` and `script_runner` from `config["configurable"]` where it does today.
- Out of scope: the trace recorder (phase 208), which consumes the single child-run outcome defined here; and the workflow graph's step logic, beyond declaring lifetimes and using the generated reset.
