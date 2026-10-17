# Feature Specification: Screen Context Awareness

**Feature Branch**: `195-screen-context-awareness`

**Created**: 2026-10-17

**Status**: Ready to implement (pending review by the Floor Reviewer and the user's answers to the open questions in Clarifications)

**Input**: Maestro brief 2026-10-17, relaying the user: "We also need to improve the capacity of context awareness within screens." Scope proposed by the Maestro (typed contract, resolver registry, deixis, trace, web hook, honesty, tests) and refined here. Absorbs the goal screen note that phase 188 carried and backend gap 13 (screen context on the trace) that phase 194 carried. Addition relayed by the Maestro the same day: "I think that components on the screen could have a chat about this action maybe" — a "Chat about this" action on every module and component (US8, FR-020 to FR-025).

**Governed by**: `specs/arch/claim-topology.md` (posture travels with every claim; set by code), `specs/arch/system-one-models.md` (routing Choice bars are calibrated; no live calibration without the user's OK), `specs/arch/pre-v1-hard-cuts.md`, `PRODUCT.md` (principle 2: show the claim's posture; Ze uses what it knows silently), phase 141 (memory read contract: no unsolicited recitation), phase 183 (Ask bar and contextual overlay send the context), phase 184 (`context.compose`/`topic`, the eval `context` key).

**Depends on**: 183 (Ask bar, overlay, places) and 184 T037 (eval requests carry `context`). **Must land before 186 and 187**: World, Ask and every later place publish into this contract.

**Doctrine functions served**: perception (what the user is looking at is an input, read honestly) and governance (the trace says what Ze could see and from where).

---

## Overview

Today the web client sends `context: { screen, goal_id?, workflow_id?, execution_id?, workspace_placed? }` with a message. `api/ws/turns.py` passes it to `config["configurable"]["screen_context"]`, and `fetch_context` builds one note, for workflows only (`_build_screen_context_note`, raw `error` text included). `goal_id` is sent and ignored. Routing never sees the screen, the trace never records it, a retry drops it, and nothing tells the model that "this" means the goal on the page.

With the Ask bar on every place and the contextual overlay (183), most questions will be asked *about* something on screen. This phase makes that explicit:

1. **One typed contract** (`ScreenContext`): place, route, subject refs, selection, visible items, focused module, canvas modules (Ask), the time the context was captured.
2. **A resolver registry in the engine**: every ref kind maps to a resolver that loads the record and returns a compact line with its claim posture, set by code. Core packages register resolvers for their kinds; plugins register theirs through `ze_sdk`.
3. **Deixis**: the note tells the model what "this", "that one" and "these" refer to; the subject can lean routing toward the owning agent (behind a flag until a calibration the user approves).
4. **Trace**: what was sent, which resolvers ran, what was missing, stale or cut.
5. **Web**: a screen-context store each place publishes into; the Ask bar and overlay send its snapshot.
6. **Honesty**: Ze never claims to see what is not in the note; a record that changed after the user looked is marked as changed; a missing record is said to be missing.
7. **Chat about this**: every module and component carries a small bracketed chip (and a shortcut) that opens the Ask overlay with that component as the explicit subject and suggests first questions for its kind.

## Clarifications

### Session 2026-10-17 (Spec Architect, from the code and the Maestro's proposal)

- Kept from the proposal: all seven items. Refined: the resolver step runs in a new graph node `resolve_screen` **before** routing (after `preprocess` / `inject_routing_context`), because routing runs before `fetch_context` and could not use the subject otherwise. `fetch_context` copies the note into the agent context.
- Cut from the proposal: per-element pixel data and free-text "what the user is reading" (privacy and size; refs only). `notification` stays a kind but resolves to the notification's own target (one hop), not to the bell list.
- Added: the context is stored on the user message and replayed on Retry (today a retry drops it; phase 184 records that as a known gap). This is a new column, `messages.screen_context` (`zc` chain).
- Hard cut: `goal_id`, `workflow_id`, `execution_id` at the top level of `context` are replaced by subject refs; `_build_screen_context_note` is deleted.

### Open questions for the user (Spec Architect's recommendation in bold; tasks follow the recommendation)

- OQ-1: May the screen subject lean routing (for example, a question asked on a goal page leans to the goals agent)? It changes the text the calibrated routing Choice sees, so it needs a calibration run that costs credits. → **Recommended: build it behind `system_one.surfaces.routing.screen_hint: false`, add screen rows to the routing calibration set, and enable it only after you approve one live `make calibrate-routing` run and it passes the existing acceptance rule.** Alternative: never use the screen for routing (deixis still works through the note once routed). Alternative: enable without calibration (not recommended; ADR rule 10).
- OQ-2: Store the screen context on each user message so Retry replays it? → **Recommended: yes (new nullable JSONB column; the context is refs and labels, no record contents).** Alternative: do not store; a retry answers without the screen (today's behaviour).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - "Why is this slipping?" means the thing on screen (Priority: P1)

On World, the user selects the "Reply to Ana about the invoice" mark in the field and asks "why is this slipping?" from the Ask bar. The overlay answers about that loop: its drift deadline, rationale and evidence age, without asking which one. On a goal page, "what's blocking this?" answers about that goal's open gate and next milestone. On Mind with two beliefs selected, "are these still true?" answers about those two.

**Why this priority**: It is the user's request and the reason the Ask bar lives on every place.

**Independent Test**: Unit-test the note builder with fake resolvers: subject `loop:L1` → the note starts with `[Screen: World. The user is looking at: Open loop · "Reply to Ana about the invoice" …]` and the deixis line `"this" / "it" = that loop unless the user names something else`; selection of two facts → `"these" = the 2 selected beliefs`. Eval scenarios per place (FR-019) with the judge seeing the context: the answer is about the referenced record and does not ask "which one?".

**Acceptance Scenarios**:

1. **Given** a subject and a selection, **When** the user says "this", **Then** the note binds "this" to the subject and "these" to the selection.
2. **Given** no subject, selection or focus (for example the bare World view), **When** the user says "this", **Then** the note says nothing is singled out on screen, and Ze asks one short clarifying question instead of guessing.
3. **Given** the user names a different item explicitly, **When** the turn runs, **Then** the named item wins (the deixis line says "unless the user names something else").

---

### User Story 2 - Every claim in the note shows its posture (Priority: P1)

Each resolved line carries the record's kind, source, confidence and last update, set by code: `Open loop · "Reply to Ana" — drifting since Tue; suspicion→confirmed by you; confidence 0.62; source email; updated 3 d ago`. A suspected loop is described as a suspicion, never as a fact.

**Independent Test**: Resolver unit tests per core kind assert the posture fields come from the record (fake store), and the formatter renders them; a `suspicion` record renders "suspected", never "is".

**Acceptance Scenarios**:

1. **Given** a loop in state `suspected`, **When** resolved, **Then** the line says "suspected (not confirmed)".
2. **Given** a fact with confidence 0.4, **When** resolved, **Then** the confidence is printed and the line is not phrased as certain.

---

### User Story 3 - Missing, changed and cut context is said plainly (Priority: P1)

If a referenced record was deleted, the note says "Goal g9 (no longer exists)". If the record changed after the client captured the context (record `updated_at` later than `captured_at`), the line says "changed since you opened it". If the budget cuts lines, the note ends with "+N more on screen not included". If a resolver fails or times out, "Could not load workflow w1." Ze never describes content that is not in the note.

**Independent Test**: Registry tests with fakes: deleted → missing line; `updated_at > captured_at` → stale marker; 40 visible refs → truncation line with the right count; a resolver raising → "could not load" line and the turn completes; a resolver sleeping past its timeout → same.

---

### User Story 4 - The trace says where the question came from (Priority: P1)

The reply's trace records the screen context and each resolver run (kind, id, status `ok | missing | stale | failed | timeout | cut`, duration), and the trace module shows "Asked from: Goal · LedgerLite launch" (phase 187 renders it; this phase provides the data and a minimal line in today's trace panel).

**Independent Test**: `record_trace` test: a turn with a screen context yields `MessageTrace.screen` with place, subject labels and resolver rows; REST `getMessageTrace` and the partial `trace_update` frame carry it.

---

### User Story 5 - Places publish what is on screen (Priority: P1)

Each place publishes its subject, selection, visible items and focused module into one client store; the Ask bar and the overlay send a snapshot of it at submit time (with `captured_at`). This phase wires the interim pages that have a clear subject (goal detail, workflow detail with `?execution=`, plugin pages with a declared subject); phases 186–190 publish richer selection and visibility from their new modules.

**Independent Test**: Vitest: on `/doing/goals/g1` the snapshot has `place: "doing"`, `subject: [{ kind: "goal", id: "g1", label }]`; on `/doing/workflows/w1?execution=e1` two subject refs (workflow, execution); unmounting a page clears its publications; the Ask bar submit sends the snapshot, and the overlay keeps the explicit `askAbout` context merged over it (183 FR-008).

---

### User Story 6 - Retry keeps the screen (Priority: P2)

Retrying a reply re-runs the turn with the same stored screen context (OQ-2), so the regenerated answer is about the same thing. A stored context older than the record's current state is marked stale like any other.

**Independent Test**: `api/ws/turns.py` retry test: the stored `screen_context` of the user message is passed as `config_extra["screen_context"]`; a message without one passes none.

---

### User Story 7 - The subject can lean routing, once calibrated (Priority: P3)

With `system_one.surfaces.routing.screen_hint: true`, `resolve_screen` appends one line (`Screen subject: goal "LedgerLite launch"`) to `routing_hints`, which the routing Choice already reads as its `context` field. Off by default; enabled only after the user approves a live calibration run that passes (OQ-1).

**Independent Test**: With the flag off, `routing_hints` is unchanged by `resolve_screen` (test); with it on, the line is appended once and capped. The calibration set gains screen rows (`eval/calibration/routing_screen.jsonl`, EN and PT) checked offline by `--check-sets`; no live run in this phase's gates.

### User Story 8 - "Chat about this" on any component (Priority: P1)

Every module and component on every place carries a "Chat about this" command chip in its frame head: revealed on hover or focus-within on pointer devices, always visible on touch, reachable from the keyboard with `c` while focus is inside the module (outside text fields). Invoking it opens the Ask overlay on the thread selected in Ask, with the component as the explicit subject (`{ kind, id, label, component }`), `origin: "chat_about"`, and up to three suggested first questions for that kind as command chips (keys 1–3), with the Ask bar empty and focused. The curious-pet orb glances at the module. Ze's first reply leads with the component's subject. The trace reads "Asked about: <kind> · <title>".

Suggested questions (EN; PT equivalents in the same table): loop — "Why is this slipping?", "What would close it?", "Who is it waiting on?"; goal — "What's blocking this?", "What happens next?", "Is it on track?"; workflow — "What does this do?", "When did it last fail and why?"; workflow execution — "Why did this run fail?", "What did it produce?"; held write — "What exactly will this send?", "Why does it need my OK?"; belief / fact — "Why do you think this?", "Where did this come from?", "How sure are you?"; person / entity — "What's open with them?", "When did we last talk?"; hypothesis — "What evidence do you have?", "How could I check this?"; notification — "What is this about?"; procedure — "When do you use this?"; skill — "What does this skill let you do?"; workspace run — "What did this run do?"; a canvas card — the card's own subject kind's questions; anything else — "Tell me about this."

**Why this priority**: The user asked for it; it turns every module into a question Ze can answer about itself.

**Independent Test**: Vitest: `Module` with `onChatAbout` renders the chip with accessible name "Chat about <label>", hidden-until-hover class on pointer and visible on touch (mocked `(hover: none)`), fires on click and on `c` inside the module (not inside an input); `chatAbout({ kind: "loop", id: "L1", label, component: "loop_row" })` opens the overlay with that subject, `origin: "chat_about"`, the loop suggestions, empty focused bar, and calls `glance(moduleElement)`. Backend: `build_screen_note` with `origin: "chat_about"` adds the lead-with-subject line; `ScreenTrace.origin` makes the trace label "Asked about". Eval: one `chat_about` scenario per core kind (FR-024).

**Acceptance Scenarios**:

1. **Given** a loop row's chip is invoked and the user picks "Why is this slipping?", **When** Ze replies, **Then** the reply's first sentence names that loop and answers from its record.
2. **Given** the overlay was opened by "Chat about this" and the user types a different question, **When** sent, **Then** the subject stays the component until the overlay closes (explicit context, 183 FR-008).
3. **Given** reduced motion, **When** invoked, **Then** the orb does not glance (gaze off) and everything else works.

### Edge Cases

- A component whose kind has no resolver (for example a plugin kind with the plugin off): the chip still works; the note says the item could not be loaded (FR-008).
- `context` absent (API clients, proactive turns, eval without context): no note, no trace section, nothing else changes.
- Unknown `kind`: one line "Unrecognised item on screen (kind X)" and a `failed` trace row; never an exception.
- A plugin is disabled: its kinds have no resolver; same as unknown.
- Duplicate refs across subject/selection/visible: resolved once, listed at the highest-priority slot.
- Visible refs over the cap: the client caps at 30; the server re-caps and records `cut`.
- `workspace_placed` (files the user just placed) keeps its existing note, built by a `workspace_placed` resolver instead of inline code.
- The screen note is runtime-only: never checkpointed, never written to memory, never fed to the fact or loop intake as user speech (`write_memory` and the commitment intake read only the user's text).
- Compound turns: every subtask's agent context gets the same note (existing `_prompt_note_kwargs` path).
- Labels sent by the client are display hints only; the server resolves records by id and never trusts a client label as a fact.

## Requirements *(mandatory)*

### Functional Requirements

**Contract**

- **FR-001**: The inbound `message.context` MUST be `WsScreenContext` (ze-api `api/ws/schemas.py`) with: `place` (`world | ask | doing | mind | governance | plugin`), `route` (path without query secrets, ≤ 200 chars), `subject: list[ScreenRef]` (≤ 3), `selection: list[ScreenRef]` (≤ 20), `visible: list[ScreenRef]` (≤ 30), `focused_module: str | None` (≤ 80), `canvas: list[CanvasRef]` (≤ 12; Ask only: `{ index, type, ref? }`), `captured_at` (ISO 8601), plus the existing `compose`/`topic` (184) and `workspace_placed`. `ScreenRef = { kind: str, id: str, label: str | None }`. The old top-level `screen`, `goal_id`, `workflow_id`, `execution_id` fields are removed (pre-v1 hard cut); the generated WS types and the conformance test follow.
- **FR-002**: The same shape MUST exist as a dataclass `ScreenContext` in `ze-agents` (`ze_agents/screen.py`) parsed once in `api/ws/turns.py`, so the engine never reads a raw dict.

**Resolvers**

- **FR-003**: `ze-agents` MUST define the `ScreenResolver` protocol (`kinds: tuple[str, ...]`; `async resolve(refs: list[ScreenRef], ctx: ResolveContext) -> list[ScreenLine]`) and `ScreenLine` (`ref`, `label`, `summary` ≤ 240 chars, `posture: ScreenPosture | None` with `kind`, `source`, `confidence`, `updated_at`, and `status`). Re-exported from `ze_sdk` for plugins.
- **FR-004**: `ze-core` MUST add `ze_core/screen/` with `ScreenResolverRegistry` (kind → resolver; duplicate kind registration fails startup with a typed error) and `build_screen_note(context, registry, now) -> ScreenResolution` (note text + trace rows). Resolution runs resolvers in parallel per kind with a 300 ms timeout each and an 800 ms total budget.
- **FR-005**: Core resolvers MUST live in the package that owns the data and be registered by ze-api wiring: ze-automation (`goal` with status, milestones done/total, next milestone, open gate; `goal_gate`; `workflow` with schedule, last result; `workflow_execution` with status, step count, duration and `failure_summary` from 184, never raw error text; `held_write`), ze-worldstate (`loop` with state, drift deadline and rationale, provenance, confidence), ze-memory (`entity` incl. people and projects with one-hop relation names; `fact` with family, confidence, review state; `procedure`), ze-skills (`skill`), ze-workspace (`workspace_run`; `workspace_placed` replacing the inline note), ze-proactive (`notification` → one hop to its target ref, resolved by that target's resolver), ze-correlation (`hypothesis`, after phase 185 or with the existing store if available).
- **FR-006**: `ZePlugin` MUST gain `screen_resolvers() -> list[ScreenResolver]` (default empty), collected by the container like `signal_sources()`. Plugins register: ze-personal `contact`, ze-calendar `reminder`, ze-news `news_article`.
- **FR-007**: The note MUST respect a budget of 1200 characters (`SCREEN_NOTE_CAP`), filled in priority order: subject, selection, focused module, visible, canvas. Lines that do not fit are dropped and counted ("+N more on screen not included"); every dropped ref gets a `cut` trace row.
- **FR-008**: Status rules: record not found → `missing` ("(no longer exists)"); `posture.updated_at > captured_at` → `stale` ("changed since you opened it"); resolver error → `failed` ("Could not load …"); timeout → `timeout` (same wording). None of these raise.

**Engine**

- **FR-009**: A new graph node `resolve_screen` MUST run after `preprocess` (after `inject_routing_context` when a plugin adds it) and before `embed_route`. It reads `configurable["screen_context"]` and `configurable["screen_resolvers"]`, writes `screen_note: str | None` and `screen_trace: ScreenTrace | None` to `AgentState`, and both keys are reset per turn in `make_graph_input` (`ze_core/conversation/turn.py`).
- **FR-010**: `fetch_context` MUST set `agent_context.screen_context_note` from `state["screen_note"]`. `_build_screen_context_note` and the inline workflow and `workspace_placed` branches in `fetch_context` are deleted.
- **FR-011**: The note MUST be framed for deixis: a header `[Screen: <place>. What the user can see right now, read by Ze from its own records:]`, the lines, then the binding lines: `"this" / "it" / "that" = <subject label> unless the user names something else`; `"these" / "those" = the N selected items` when a selection exists; when nothing is singled out, `Nothing on screen is singled out; if the user says "this", ask which item they mean.` Instruction tail: `Use this silently. Do not describe the screen back to the user or claim to see anything not listed here.`
- **FR-012**: When `system_one.surfaces.routing.screen_hint` is true, `resolve_screen` MUST append `Screen subject: <kind> "<label>"` (first subject only, ≤ 120 chars) to `routing_hints`. Default false. `eval/calibration/routing_screen.jsonl` (EN + PT rows asked from a screen) is added and validated by `make calibrate-routing --check-sets`; enabling is a separate commit after the user approves a live run (OQ-1).
- **FR-013**: `judgment_state._tier_focus` keeps reading `screen_context_note` (the tier judge sees the same note).

**Trace and storage**

- **FR-014**: `MessageTrace.screen: ScreenTrace | None` (`place`, `route`, `subject` labels, counts of selection/visible/canvas, `focused_module`, `captured_at`, `note_chars`, `resolvers: [{ kind, id, status, ms }]`) MUST be recorded by `record_trace`, serialized in `MessageTraceResponse` and the partial `trace_update` frame; `make codegen`.
- **FR-015**: Migration `zc039_message_screen_context.py` (ze-core `zc` chain; T001 re-reads the head) MUST add `messages.screen_context JSONB NULL`; `api/ws/turns.py` stores the parsed context on the user message; the retry path passes it back as `config_extra["screen_context"]` (OQ-2). This replaces the 184 note that a retry of a preset answers from normal routing: with 195 a retried preset re-runs its composer.

**Web**

- **FR-016**: `entities/screen-context` MUST provide a zustand store and `useScreenPublisher({ subject?, selection?, visible?, focusedModule?, canvas? })` (pages and widgets publish; cleared on unmount) and `screenSnapshot(placeOf(pathname), route)` returning the `WsScreenContext` with `captured_at = now`. Caps applied client-side.
- **FR-017**: `features/ask-bar` MUST send `screenSnapshot()` (merged under the explicit `askAbout` context, 183 FR-008) instead of `resolve-screen.ts`, which is deleted. The overlay's queued item keeps the snapshot taken at submit.
- **FR-018**: Interim pages MUST publish their subject: goal detail (`goal`), workflow detail (`workflow`, plus `workflow_execution` from `?execution=`), plugin pages (a manifest-declared subject when present). The 183 trace panel shows one line "Asked from: <place> · <first subject label>" from `MessageTrace.screen` (the HUD trace module in 187 replaces it).

**Chat about this**

- **FR-020**: `ScreenRef` MUST gain `component: str | None` (the component type, for example `loop_row`, `field_mark`, `goal_module`, `claim_card`, `notification_row`) and `WsScreenContext` MUST gain `origin: "ask_bar" | "chat_about" | "preset"` (default `ask_bar`; 184 presets send `preset`).
- **FR-021**: `shared/ui/hud/Module` MUST accept `onChatAbout?: () => void` and `chatAboutLabel?: string`; when set it renders a `CommandChip`-style bracketed chip "Chat about this" in the head's right slot (44 px target), visible on `:hover`/`:focus-within` for `(hover: hover)` devices and always visible for `(hover: none)`, and handles `c` (no modifiers, not in an input/textarea/contenteditable) while focus is within the module. Components rendered without a `Module` frame (field-chart marks, list rows) expose the same action through their own focus/hover affordance using the same chip component (`shared/ui/hud/ChatAboutChip`). No new visual language (DESIGN.md chips and controls).
- **FR-022**: `features/ask-bar` MUST add `chatAbout(ref: ScreenRef, element?: Element)`: opens the overlay with explicit context `{ subject: [ref], origin: "chat_about" }` merged over the screen snapshot, empty and focused bar, suggestion chips from `features/ask-bar/model/suggestions.ts` (kind → up to 3 EN/PT questions, fallback "Tell me about this."), and calls the presence `glance(element)` (183 FR-006a). Picking a suggestion fills and submits it.
- **FR-023**: With `origin: "chat_about"`, `build_screen_note` MUST add the line `The user opened this chat from that item's "Chat about this" action: lead your first reply with it.` and `ScreenTrace` MUST record `origin`; the trace label is "Asked about: <kind> · <title>" for `chat_about` and "Asked from: <place> · <title>" otherwise.
- **FR-024**: `eval/scenarios/screen_context.yaml` MUST add one `chat_about` scenario per core kind (loop, goal, workflow, workflow execution, held write, fact, entity, procedure, skill, workspace run, notification; hypothesis when available), EN and PT for loop, goal and fact, with criteria: the first sentence names the subject; the answer comes from the record; no "which one?".
- **FR-025**: Adoption: in this phase, the shared chip, `Module` props, `chatAbout`, suggestions and the backend line; the interim goal and workflow detail pages and the 184 claim cards rendered in chat get the action. Phases 186 (World modules, field marks, loop rows, Needs you, While you were away), 187 (canvas cards, overlay replies), 188 (goal, workflow, run, skill, procedure candidate modules and rows), 189 (beliefs, people, entity, procedures) and 190 (spend anomaly, data domain, file rows) wire `onChatAbout` on every module and component they build, with a test per kind.

**Evals**

- **FR-019**: `eval/scenarios/screen_context.yaml` MUST cover deixis per place (World loop selected; Doing goal page; Doing workflow execution; Mind two beliefs selected; Governance spend anomaly selected when 190 adds it — skipped until then), each EN and PT, sent with a scenario `context:` (184 T037), with judge criteria: the answer is about the referenced record, does not ask "which one?" when a subject exists, asks when nothing is singled out, does not describe the screen back, and does not state anything absent from the note.

### Key Entities

- **ScreenContext / ScreenRef / CanvasRef**: the client's snapshot of what is on screen, refs and labels only.
- **ScreenResolver / ScreenLine / ScreenPosture**: per-kind loading of a record into one honest line with posture.
- **ScreenResolution**: note text + trace rows; runtime only.
- **ScreenTrace**: what reached the trace, including `origin`.
- **Suggestion table**: kind → up to three first questions (EN/PT), client-side data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The deictic eval scenarios pass with the judge (EN and PT), recorded in the floor's Handoffs note.
- **SC-002**: For every core kind, a resolver exists with unit tests (fake store) and the five owning packages' real-Postgres tests cover the query shapes that are new (`make test-pg`).
- **SC-003**: No note exceeds 1200 characters; truncation is counted and traced (property test over random ref sets).
- **SC-004**: `git grep -n "_build_screen_context_note\|goal_id.*screen_context\|\"execution_id\"" -- core apps` finds no remaining top-level context reads.
- **SC-006**: Every module and component built in this phase and in 186–190 exposes "Chat about this" (each phase's tests list its kinds); the `chat_about` eval scenarios pass with the judge.
- **SC-005**: `make test-py`, `make test-pg`, `make lint`, `make test-web`, `make typecheck-web` pass; `make calibrate-routing --check-sets` passes offline.

## Assumptions

- Resolver queries are single-row or small `ANY($1)` reads on indexed ids; 800 ms total is enough on the local database.
- Labels are short; the client never sends record contents.
- Phase 185 may land after this phase; the `hypothesis` resolver then uses the correlation store directly and moves to its REST-backed shape later with no contract change.

## Out of Scope

- Pixel, text-selection or scroll-position capture; screenshots.
- Using the screen for memory or loop intake.
- Enabling the routing hint (needs the user's OK, OQ-1).
- The HUD rendering of "Asked from" (187) and richer publishing from new modules (186–190).

## Verbatim Constraints

- "We also need to improve the capacity of context awareness within screens." (user, via the Maestro, 2026-10-17)
- "Ze is not an agenda or notes app; every view answers 'what does Ze understand, and what is it doing about it?'" (user, 2026-10-17)
