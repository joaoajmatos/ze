# Feature Specification: Screen Context Awareness

**Feature Branch**: `195-screen-context-awareness`

**Created**: 2026-10-17

**Status**: Implemented (approved by the Floor Reviewer Gauge, d066787f; user answers recorded 2026-10-17; `zc039` reserved)

**Input**: Maestro brief 2026-10-17, relaying the user: "We also need to improve the capacity of context awareness within screens." Scope proposed by the Maestro (typed contract, resolver registry, deixis, trace, web hook, honesty, tests) and refined here. Absorbs the goal screen note that phase 188 carried and backend gap 13 (screen context on the trace) that phase 194 carried. Addition relayed the same day: "I think that components on the screen could have a chat about this action maybe" — a "Chat about this" action on every module and component (US8, FR-021 to FR-026).

**Governed by**: `specs/arch/claim-topology.md` (posture travels with every claim; set by code), `specs/arch/system-one-models.md` (calibrated judges: no change to the text they see without a calibration; no live calibration without the user's OK), `specs/arch/pre-v1-hard-cuts.md`, `PRODUCT.md` (principle 2; Ze uses what it knows silently), phase 141 (no unsolicited recitation), phase 182 (tier judge state), phase 183 (Ask bar, overlay, `Module`, places), phase 184 (`context.compose`/`topic`, `_compose_preset`, claim-card posture vocabulary, `failure_summary`, `list_progress`, notification `target_parent_id`, eval `context`).

**Depends on**: 183 landed; 184 landed (its `_compose_preset`/`_preset_envelope` in `fetch_context`, `failure_summary`, `list_progress`, `zpro005`, T037 eval `context`). **Must land before 186 and 187**: World, Ask and every later place publish into this contract. Resolver lines degrade (omit the field) if a 184 field is absent.

**Doctrine functions served**: perception (what the user is looking at is an input, read honestly) and governance (the trace says what Ze could see and from where).

---

## Overview

Today the web client sends `context: { screen, goal_id?, workflow_id?, execution_id?, workspace_placed? }` with a message. `api/ws/turns.py` passes it as a raw dict to `config["configurable"]["screen_context"]`, and `fetch_context` builds one note, for workflows only (`_build_screen_context_note`, raw `error` text included). `goal_id` is sent and ignored. Routing never sees the screen, the trace never records it, a retry drops it, and nothing tells the model that "this" means the goal on the page.

With the Ask bar on every place and the contextual overlay (183), most questions will be asked about something on screen. This phase makes that explicit:

1. **One typed contract** (`ScreenContext`): place, route, origin, subject refs, selection, visible items, focused module, canvas modules (Ask), capture time. Each ref may carry its parent id and the version the client displayed.
2. **A resolver registry in the engine**: each ref kind maps to a resolver that loads the record and returns one compact, sanitised line with its claim posture, set by code. Core packages register resolvers for their kinds; plugins register theirs through `ze_sdk`.
3. **Deixis**: the note tells the model what "this", "that one" and "these" refer to (in the user's language); the subject can lean routing behind a flag until a calibration the user approves.
4. **Trace**: what was sent, which resolvers ran, what was missing, changed, failed or cut.
5. **Web**: one screen-context store places publish into; every send path in the client merges its snapshot.
6. **Honesty**: Ze never claims to see what is not in the note; a record that changed after it was shown to the user is marked; a missing record is said to be missing; record text cannot forge instructions.
7. **Chat about this**: every module and component carries a small bracketed chip (and a shortcut) that opens a chat with that component as the explicit subject and suggests first questions for its kind.

## Clarifications

### Session 2026-10-17 (Spec Architect, from the code and the Maestro's proposal)

- Kept from the proposal: all seven items. Refined: resolution runs in a new graph node `resolve_screen` before routing (after `preprocess` / `inject_routing_context`), because routing runs before `fetch_context`. `fetch_context` copies the note into the agent context.
- Cut from the proposal: pixel, text-selection or scroll capture (refs and labels only). `notification` resolves one hop to its target, not the bell list.
- Added: the context is stored on the user message and replayed on Retry (new column `messages.screen_context`).
- Hard cut: top-level `screen`, `goal_id`, `workflow_id`, `execution_id` in `context`; `_build_screen_context_note`; the web `resolve-screen.ts`.

### Session 2026-10-17 (Floor Reviewer Gauge, changes applied)

- The calibrated tier judge (`needs_deep_reasoning`, enabled 2026-10-16) must not see new text: `_tier_focus` stops reading the screen note and never sees the screen hint (option (a); the complexity calibration sets contain no screen-note rows, so their calibrated inputs are unchanged). The routing screen hint is added inside the routing judgment state only; `routing_hints` itself is untouched.
- Staleness compares the record's `updated_at` with the version the client displayed (`ref.as_of`), not with a client clock.
- `workflow_execution` (and `goal_gate`) refs carry `parent_id`; notification one-hops pass `target_parent_id`.
- On `/ask` (no overlay, no Ask bar) "Chat about this" sets the subject on the Ask composer. All client sends go through one path that merges the snapshot.
- `origin: "chat_about"` is sent only with the first message after the chip is used.
- The note lives in checkpointed state (needed for confirmation resume); it is reset each turn and never written to memory or intake.
- Bad or partial contexts never fail a turn. Record text is sanitised. Eval scenarios get a fixture setup step.
- 184's preset summary gets its own `AgentContext.preset_note` field so it neither overwrites nor is overwritten by the screen note.

### Session 2026-10-17 (user answers, relayed by the Maestro)

- Q (OQ-1): May the screen subject lean routing? → A: **(user)** build it off behind `system_one.surfaces.routing.screen_hint`, enable it only after the user approves one live `make calibrate-routing` run that passes (the recommendation).
- Q (OQ-2): Store the screen context on each user message so Retry replays it? → A: **(user)** yes (the recommendation).
- Migration `zc039` (`messages.screen_context`) reserved by the Maestro.

### Open questions for the user (answered above; kept for the record) (Spec Architect's recommendation in bold; tasks follow the recommendation)

- OQ-1: May the screen subject lean routing (a question asked on a goal page leans to the goals agent)? It changes the text the calibrated routing Choice sees, so it needs a live calibration run that costs credits. → **Recommended: build it behind `system_one.surfaces.routing.screen_hint: false`, add screen rows to the routing calibration set (validated offline), and enable it only after you approve one live `make calibrate-routing` run that passes the existing acceptance rule.** The tier judge never sees the screen either way. Alternative: never use the screen for routing (deixis still works once routed).
- OQ-2: Store the screen context on each user message so Retry replays it? → **Recommended: yes (nullable JSONB; refs, labels and versions, no record contents).** Alternative: a retry answers without the screen (today's behaviour).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - "Why is this slipping?" means the thing on screen (Priority: P1)

On World, the user selects the "Reply to Ana about the invoice" mark and asks "why is this slipping?" from the Ask bar. The overlay answers about that loop without asking which one. On a goal page, "what's blocking this?" answers about that goal's open gate and next milestone. On Mind with two beliefs selected, "are these still true?" answers about those two. In Portuguese, "porque é que isto está a escorregar?" binds the same way.

**Why this priority**: It is the user's request and the reason the Ask bar lives on every place.

**Independent Test**: Note-builder unit tests with fake resolvers: subject `loop:L1` → the note binds "this" to that loop; two included selected facts → "these" binds to "the 2 selected items shown above"; a lone selection with no subject binds "this" to it. Eval scenarios per place (FR-020) with the judge given the context: the answer is about the referenced record and does not ask "which one?".

**Acceptance Scenarios**:

1. **Given** a subject and a selection, **When** the user says "this", **Then** the note binds "this" to the subject and "these" to the included selection.
2. **Given** nothing singled out, **When** the user says "this", **Then** Ze asks one short clarifying question.
3. **Given** the user names a different item, **When** the turn runs, **Then** the named item wins.

---

### User Story 2 - Every claim in the note shows its posture (Priority: P1)

Each resolved line carries the record's kind, source, confidence and age, set by code, in the same posture words the 184 claim cards use (a suspected loop is "suspected (not confirmed)", never a fact).

**Independent Test**: Resolver unit tests per core kind assert posture fields come from the record (fake store); the formatter renders them with the shared posture vocabulary.

**Acceptance Scenarios**:

1. **Given** a loop in state `suspected`, **When** resolved, **Then** the line says "suspected (not confirmed)".
2. **Given** a fact with confidence 0.4, **When** resolved, **Then** the confidence is printed and the line is not phrased as certain.

---

### User Story 3 - Missing, changed, failed and cut context is said plainly (Priority: P1)

A deleted record: "Goal (no longer exists)". A record whose `updated_at` is later than the version the client displayed (`ref.as_of`): "changed since it was shown to you". A ref that did not fit the budget is not loaded and is counted: "+N more on screen not included". A resolver error or timeout: "Could not load workflow." Ze never describes content that is not in the note.

**Independent Test**: Registry tests with fakes: deleted → missing; `updated_at > as_of` → changed; no `as_of` → no change check; 40 visible refs → only what fits is resolved, the rest counted and traced `cut` without a store call; raising and sleeping resolvers → "could not load" and the turn completes. Retry test: a stored ref whose record changed since → changed.

---

### User Story 4 - The trace says where the question came from (Priority: P1)

The reply's trace records the screen context and each resolver run (`ok | missing | changed | failed | timeout | cut`, duration). The trace shows "Asked from: Goal · LedgerLite launch" or, after "Chat about this", "Asked about: Loop · Reply to Ana" (phase 187 renders it in the HUD; this phase adds a minimal line to today's trace panel).

**Independent Test**: `record_trace` test: `MessageTrace.screen` has place, subject labels, `origin` and resolver rows; REST `getMessageTrace` and the partial `trace_update` frame carry it.

---

### User Story 5 - Every send carries what is on screen (Priority: P1)

Places publish subject, selection, visible items and focused module into one client store. Every send path in the client (Ask bar, overlay, the `/ask` composer, the Try presets, workspace uploads) goes through one function that merges the store's snapshot under any explicit context. This phase wires the interim pages with a clear subject (goal detail; workflow detail with `?execution=`; plugin pages with a declared subject); phases 186–190 publish richer selection and visibility from their new modules.

**Independent Test**: Vitest: on `/doing/goals/g1` the snapshot has `place: "doing"` and the goal subject with its `as_of`; on `/doing/workflows/w1?execution=e1` the execution ref carries `parent_id: "w1"`; unmounting clears publications; one test per send path asserts the snapshot is merged (presets send `origin: "preset"`; a workspace upload merges `workspace_placed` into the same context).

---

### User Story 6 - Retry keeps the screen (Priority: P2)

Retrying a reply re-runs the turn with the stored screen context (OQ-2), so the regenerated answer is about the same thing; refs whose records changed since are marked changed.

**Independent Test**: `api/ws/turns.py` retry test: the stored context is passed as `config_extra["screen_context"]`; none when the message has none.

---

### User Story 7 - The subject can lean routing, once calibrated (Priority: P3)

With `system_one.surfaces.routing.screen_hint: true`, the routing judgment state's `context` field gains one line (`Screen subject: goal "LedgerLite launch"`) after the existing routing hints. `routing_hints`, the routing fallback prompt and the tier state are unchanged. Off by default; enabled only after the user approves a live calibration run that passes (OQ-1).

**Independent Test**: With the flag off, the routing judgment state equals today's; with it on, the line is added once and capped; the tier state never contains screen text in either case. `eval/calibration/routing_screen.jsonl` (EN + PT) passes the new offline `--check-sets` of `eval/calibration/routing.py`.

---

### User Story 8 - "Chat about this" on any component (Priority: P1)

Every module and component on every place carries a "Chat about this" command chip in its frame head: revealed on hover or focus-within on pointer devices (kept in the DOM and focusable), always visible on touch, reachable with `c` while focus is inside the module (outside text fields). Invoking it starts a chat with the component as the explicit subject (`{ kind, id, label, component, parent_id?, as_of? }`) and up to three suggested first questions for its kind, and the curious-pet orb glances at the module. On places other than `/ask` this opens the Ask overlay with the bar empty and focused; on `/ask` it sets the subject on the composer (a visible subject chip with a remove control), shows the suggestions above the composer and focuses it. Only the first message after invoking it carries `origin: "chat_about"`, and Ze names that item in its first sentence. The trace reads "Asked about: <kind> · <title>".

Suggested questions (EN; PT in the same table): loop — "Why is this slipping?", "What would close it?", "Who is it waiting on?"; goal — "What's blocking this?", "What happens next?", "Is it on track?"; workflow — "What does this do?", "When did it last fail and why?"; workflow execution — "Why did this run fail?", "What did it produce?"; held write — "What exactly will this send?", "Why does it need my OK?"; fact — "Why do you think this?", "Where did this come from?", "How sure are you?"; entity — "What's open with them?", "When did we last talk?"; hypothesis — "What evidence do you have?", "How could I check this?"; notification — "What is this about?"; procedure — "When do you use this?"; skill — "What does this skill let you do?"; workspace run — "What did this run do?"; a canvas card — its subject kind's questions; anything else — "Tell me about this."

**Why this priority**: The user asked for it; it turns every module into a question Ze can answer about itself.

**Independent Test**: Vitest: `Module` with `onChatAbout` renders the chip (accessible name "Chat about <label>", focusable while visually hidden under `(hover: hover)`, visible under `(hover: none)`), fires on click and on `c` inside the module (not inside an input); `chatAbout` on World opens the overlay with the subject, suggestions, empty focused bar, glance; on `/ask` sets the composer subject chip and suggestions; the first message carries `origin: "chat_about"`, the second `ask_bar` with the same subject. Backend: `origin: "chat_about"` adds the name-it-first line; the trace label is "Asked about". Eval: one `chat_about` scenario per core kind (FR-025).

**Acceptance Scenarios**:

1. **Given** a loop row's chip and the suggestion "Why is this slipping?", **When** Ze replies, **Then** its first sentence names that loop and answers from its record.
2. **Given** a follow-up typed in the same overlay, **When** sent, **Then** the subject stays, `origin` is `ask_bar`, and Ze does not re-introduce the item.
3. **Given** reduced motion, **When** invoked, **Then** the orb does not glance and everything else works.

### Edge Cases

- `context` absent (API clients, proactive turns): no note, no trace section.
- Partial context (eval or API sends `{ compose: "slipping" }` with no `place`): parsed with `place: None`; resolution runs on whatever refs exist; no error.
- Invalid fields (unknown `place`, over-cap values, malformed refs): dropped with a warning and a `context_invalid` trace note; the turn never fails because of the context.
- Unknown `kind` or a disabled plugin's kind: "Unrecognised item on screen" line, `failed` row.
- Duplicate refs across slots: resolved once at the highest-priority slot.
- `workspace_placed` keeps its text, built by a `workspace_placed` resolver.
- The note is reset every turn by `make_graph_input`, survives a confirmation pause and resume within the turn (it lives in checkpointed state like `memory_context`), and is never written to memory or passed to the fact or loop intake.
- Compound turns: every subtask's agent context gets the note (`_prompt_note_kwargs`).
- Client labels are display hints only; records are resolved by id; record text and client strings are sanitised before they enter the prompt (FR-009).
- A missing `screen_resolvers` registry (core `Container`, tests) means no note; a bug in note building is caught in the node and yields no note.

## Requirements *(mandatory)*

### Functional Requirements

**Contract**

- **FR-001**: The inbound `message.context` MUST follow `contracts/screen-context.md`: `place` (`world | ask | doing | mind | governance | plugin`, optional on the wire), `route` (≤ 200), `origin` (`ask_bar` default | `chat_about` | `preset`), `subject` (≤ 3), `selection` (≤ 20), `visible` (≤ 30), `focused_module` (≤ 80), `canvas` (≤ 12, Ask only), `captured_at`, plus 184's `compose`/`topic` and `workspace_placed`. `ScreenRef = { kind (≤ 64), id (≤ 64), label? (≤ 120), component? (≤ 40), parent_id? (≤ 64), as_of? (ISO 8601: the record's `updated_at` as the client displayed it) }`. `workflow_execution` refs require `parent_id` (the workflow id). The old top-level `screen`, `goal_id`, `workflow_id`, `execution_id` are removed; `WsScreenContext` documents the shape; generated WS types and the conformance test follow.
- **FR-002**: `ze-agents` MUST define `ScreenContext` and its parts (`ze_agents/screen.py`) with `from_wire(dict) -> tuple[ScreenContext, list[str]]` that never raises: it applies caps, drops unknown keys and invalid values (returned as warnings), accepts a missing `place`, and clamps `captured_at` to the server receipt time (logging skew). `api/ws/turns.py` parses once; warnings become a `context_invalid` trace note; the turn proceeds.

**Resolvers**

- **FR-003**: `ze-agents` MUST define the `ScreenResolver` protocol (`kinds`; `async resolve(refs, ctx) -> list[ScreenLine]`) and `ScreenLine` (`ref`, `label`, `summary` ≤ 240, `posture: ScreenPosture | None` with `kind`, `source`, `confidence`, `updated_at`, and `status`). Re-exported from `ze_sdk.screen`.
- **FR-004**: `ze-core` MUST add `ze_core/screen/` with `ScreenResolverRegistry` (duplicate kind fails startup with a typed error) and `build_screen_note(context, registry, now) -> ScreenResolution` (note + trace rows). It plans the budget before loading (FR-008), groups the refs it will load by kind, runs resolvers in parallel with 300 ms each and 800 ms total.
- **FR-005**: Core resolvers MUST live in the package that owns the data, registered by ze-api wiring, with the store calls listed in the contract: ze-automation (`goal`, `goal_gate`, `workflow`, `workflow_execution` via `get_execution(parent_id, id)` and `failure_summary`, never raw error text; `held_write`), ze-worldstate (`loop`, with "has a reminder" / "linked to a goal" flags from the loop row only), ze-memory (`entity`, `fact`, `procedure`), ze-skills (`skill`), ze-workspace (`workspace_run`, `workspace_placed`), ze-proactive (`notification` → one hop to its target ref built from `target_type`, `target_id`, `target_parent_id`), ze-correlation (`hypothesis`).
- **FR-006**: `ZePlugin` MUST gain `screen_resolvers() -> list[ScreenResolver]` (default empty). Plugins register ze-personal `contact`, ze-calendar `reminder`, ze-news `news_article`.
- **FR-007**: Status rules: not found → `missing` ("(no longer exists)"); `ref.as_of` present and `posture.updated_at > ref.as_of` → `changed` ("changed since it was shown to you"); error → `failed`; timeout → `timeout` ("Could not load …"); never raised.
- **FR-008**: Budget `SCREEN_NOTE_CAP = 1200` characters. The fixed lines (header, binding lines, honesty line, the chat-about line when present, the "+N more" line) are reserved first; refs are then admitted in priority order (subject, selection, focused module, visible, canvas) while their estimated line (≤ 240 chars for subject, ≤ 120 for selection and others) fits; refs not admitted are not loaded, are counted in "+N more on screen not included", and get `cut` trace rows. Binding lines describe only what was included ("these" = "the N selected items shown above", plus "M more not shown" when cut).
- **FR-009**: Every string entering the note (summaries, labels, titles, file names, `kind`, `id`, `route`, `focused_module`) MUST be sanitised: control characters and newlines collapsed to spaces, leading `[`, quotes and `"this"`-style binding patterns neutralised, each field capped. A record title containing a newline and a forged binding line or `[Screen:` header renders as one inert line (test).

**Engine**

- **FR-010**: A new graph node `resolve_screen` MUST run after `preprocess` (after `inject_routing_context` when present) and before `embed_route`, read `configurable["screen_context"]` and `configurable["screen_resolvers"]`, write `screen_note`, `screen_trace` and `screen_subject_line` to `AgentState`, catch every exception (no note, a warning), and treat a missing registry as no note. All three keys are reset in `make_graph_input`.
- **FR-011**: `fetch_context` MUST set `agent_context.screen_context_note = state.get("screen_note")`. `_build_screen_context_note` and the inline workflow and `workspace_placed` branches are deleted. 184's preset path reads `ScreenContext.compose/topic` (typed) and writes its summary to a new `AgentContext.preset_note`, rendered by `BaseAgent` after the screen note and copied by `_prompt_note_kwargs`; a test covers a preset turn that also has a screen note.
- **FR-012**: Deixis framing per the contract: header, lines, binding lines (`"this" / "it" / "that" (or the equivalent in the user's language) = …`; `"these" / "those" = the N selected items shown above`; a lone selected item with no subject binds "this"; nothing singled out → ask which item), and the honesty line `Use this silently. Do not describe the screen back to the user or claim to see anything not listed here.` With `origin: "chat_about"`: `The user started this chat from that item's "Chat about this" action: name it in your first sentence, then answer; do not recite the rest of the screen.` Posture words reuse 184's claim-descriptor vocabulary.
- **FR-013**: `judgment_state._tier_focus` MUST NOT read `screen_context_note` or the screen subject line (the tier judge's calibrated input stays as calibrated). `routing_hints` is not modified by this phase.
- **FR-014**: When `system_one.surfaces.routing.screen_hint` is true, the routing state MUST append `state["screen_subject_line"]` (`Screen subject: <kind> "<label>"`, ≤ 120) to the `context` field, through a parameter used only by `nodes/routing.py`'s call to `build_judgment_state`; the skills Choice state (`nodes/skills.py`, separately calibrated) never gets it; default false. `eval/calibration/routing.py` gains `--check-sets` (schema and row counts per language, no network) and a per-row `screen` column appended to the state's context exactly as above; the Makefile recipe passes `$(ARGS)` (today it does not, so `ARGS` would be ignored and the run would be live), and `make calibrate-routing ARGS=--check-sets` is the offline gate; enabling is a separate commit after the user approves a live run (OQ-1).

**Trace and storage**

- **FR-015**: `MessageTrace.screen: ScreenTrace | None` (in `ze_core.conversation.messages.types`, on the serde allowlist) with `place`, `route`, `origin`, `subject` labels, counts, `focused_module`, `captured_at`, `note_chars`, `resolvers`, `invalid` (warnings) MUST be recorded by `record_trace`, serialized in `MessageTraceResponse` and the partial `trace_update` frame; `make codegen`.
- **FR-016**: Migration `zc039_message_screen_context.py` (number reserved by the Maestro; T001 re-reads the head) MUST add `messages.screen_context JSONB NULL`; `apps/ze-api/tests/test_migrate.py`'s expected heads move from `zc038` to `zc039`. `api/ws/turns.py` stores the parsed context on the user message; the retry path passes it back (OQ-2), so a retried 184 preset re-runs its composer (184's retry test is updated).

**Web**

- **FR-017**: `entities/screen-context` MUST provide a zustand store, `useScreenPublisher(partial)` (pages and widgets publish refs with `as_of` from their query data and `parent_id` where needed; cleared on unmount), and `screenSnapshot(place, route)` (caps, `captured_at = now`).
- **FR-018**: One send path: `useChatWorkspace`'s `sendMessage` (and its successor in 187) MUST build `context = { ...screenSnapshot(), ...explicitContext }` for every send (Ask composer, overlay, Try presets with `origin: "preset"`, workspace uploads with `workspace_placed`). `features/ask-bar` passes its explicit context through it; `resolve-screen.ts` is deleted. Explicit context from `askAbout`/`chatAbout` is kept until the overlay closes (183 FR-008), except `origin`, which reverts to `ask_bar` after the first send.
- **FR-019**: Interim pages publish their subject: goal detail (`goal`), workflow detail (`workflow`, plus `workflow_execution` with `parent_id` from `?execution=`), plugin pages with a declared subject. The interim trace panel shows the "Asked from / Asked about" line.

**Evals**

- **FR-020**: `eval/scenarios/screen_context.yaml` MUST cover deixis per place (World loop selected; Doing goal page; Doing workflow execution; Mind two beliefs selected; Governance anomaly, skipped until 190), EN and PT, using the fixture step of FR-020a, with judge criteria: about the referenced record; no "which one?" when a subject exists; asks when nothing is singled out; does not describe the screen back; states nothing absent from the note.
- **FR-020a**: The `ze-eval` runner MUST support a scenario `setup:` block (rows inserted through the verifier's database connection, each bound to a name, removed after the scenario) and `{{name.field}}` substitution inside `context:` and `turns`; the judge receives the turn's context in its turn description. Tests for the runner; `docs/eval.md`.

**Chat about this**

- **FR-021**: `ScreenRef.component` names the component type (`loop_row`, `field_mark`, `goal_module`, `claim_card`, `notification_row`, …); `origin` per FR-001.
- **FR-022**: `shared/ui/hud/Module` MUST accept `onChatAbout?: () => void` and `chatAboutLabel?: string`, rendering `shared/ui/hud/ChatAboutChip` (bracketed `.ctl.cmd`, 44 px) in the head's right slot: under `(hover: hover)` visually hidden with opacity/transform but present and focusable, revealed on `:hover`/`:focus-within`; always visible under `(hover: none)`; `c` (no modifiers, not in an input, textarea or contenteditable) while focus is within the module. Components without a `Module` frame use `ChatAboutChip` with the same rules.
- **FR-023**: `features/ask-bar` MUST add `chatAbout(ref, element?)`: off `/ask`, opens the overlay with explicit `{ subject: [ref], origin: "chat_about" }`, empty focused bar, suggestion chips (keys 1–3) from `model/suggestions.ts`; on `/ask`, sets the composer's explicit subject (subject chip with remove), suggestions above the composer, composer focused; in both, calls the presence `glance(element)` (183 FR-006a). Picking a suggestion fills and submits it.
- **FR-024**: FSD: features and entities never import `features/ask-bar` across slices. `ConnectedPrimitiveTree` takes an `onChatAbout` prop; widgets (the chat message list, each place's widgets) read `chatAbout` and pass callbacks down to rows, marks and cards by props.
- **FR-025**: `eval/scenarios/screen_context.yaml` MUST add one `chat_about` scenario per core kind (loop, goal, workflow, workflow execution, held write, fact, entity, procedure, skill, workspace run, notification; hypothesis when available), EN and PT for loop, goal and fact: the first sentence names the subject; the answer comes from the record; no "which one?".
- **FR-026**: Adoption: in this phase, the chip, `Module` props, `chatAbout`, suggestions, the backend line, the interim goal and workflow detail pages, and the 184 claim cards in chat. Phases 186 (World modules, field marks, loop rows, Needs you, While you were away), 187 (canvas cards, overlay replies, `/ask` composer subject), 188 (goal, workflow, run, skill, procedure candidate modules and rows), 189 (beliefs, people, entity, procedures) and 190 (spend anomaly, data domain, file rows) wire `onChatAbout` on every module and component they build, through widget props (FR-024), with a test per kind.

### Key Entities

- **ScreenContext / ScreenRef / CanvasRef**: the client's snapshot of what is on screen, refs, labels, parent ids and displayed versions only.
- **ScreenResolver / ScreenLine / ScreenPosture**: per-kind loading of a record into one sanitised line with posture.
- **ScreenResolution**: note text + trace rows + subject line.
- **ScreenTrace**: what reached the trace, including `origin` and `invalid`.
- **Suggestion table**: kind → up to three first questions (EN/PT), client data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The deictic and `chat_about` eval scenarios pass with the judge (EN and PT), recorded in the floor's Handoffs note.
- **SC-002**: Every core kind has a resolver with unit tests (fake store); new SQL (`NotificationStore.get`, entity one-hop, the migration) has `@pytest.mark.pg` tests.
- **SC-003**: No note exceeds 1200 characters; cut refs are never loaded (property test with a call-counting fake).
- **SC-004**: `git grep -nE 'screen_ctx\.get|_build_screen_context_note' -- core apps` and `git grep -nE '"(goal_id|workflow_id|execution_id)"' -- core/engine/ze-core/ze_core/orchestration/nodes/context.py apps/ze-api/ze_api/api/ws` return nothing.
- **SC-005**: `make test-py`, `make test-pg`, `make lint`, `make test-web`, `make typecheck-web`, `make web-build` pass; `make calibrate-routing ARGS=--check-sets` passes offline; no live calibration run.
- **SC-006**: Every module and component built here and in 186–190 exposes "Chat about this" (each phase's tests list its kinds).

## Assumptions

- Resolver queries are single-row or small `ANY($1)` reads on indexed ids; 800 ms total is enough locally.
- Clients send refs and labels, never record contents.
- Phase 185 may land later; the `hypothesis` resolver uses the correlation store directly.

## Out of Scope

- Pixel, text-selection or scroll capture; screenshots.
- Using the screen for memory or loop intake.
- Enabling the routing hint (OQ-1) or any change to the tier judge's input.
- The HUD rendering of "Asked from / about" (187) and richer publishing from new modules (186–190).

## Verbatim Constraints

- "We also need to improve the capacity of context awareness within screens." (user, via the Maestro, 2026-10-17)
- "I think that components on the screen could have a chat about this action maybe" (user, via the Maestro, 2026-10-17)
- "Ze is not an agenda or notes app; every view answers 'what does Ze understand, and what is it doing about it?'" (user, 2026-10-17)
