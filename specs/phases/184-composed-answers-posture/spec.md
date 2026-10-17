# Feature Specification: Composed Answers and Claim Posture (B1)

**Feature Branch**: `184-composed-answers-posture`

**Created**: 2026-10-17

**Status**: Ready to implement (pending review by the Floor Reviewer and the user's answers to the open questions in Clarifications)

**Input**: Maestro brief 2026-10-17: "184 B1 composed answers + claim posture on render_* descriptors + workflow failure_summary + goal progress fields + notification deep links (backend gaps 1, 2, 9, 10, 14)." Source: `apps/ze-web/.impeccable/plan/overhaul-plan.md` section d (gaps 1, 2, 9, 10, 14), section c (assembly), decision 7 ("B1 runs before W3; W3 does not ship client-side compositions").

**Governed by**: `specs/arch/claim-topology.md` (shared `ClaimKind` vocabulary; a claim reaches the user only with the posture its kind licenses), `specs/arch/pre-v1-hard-cuts.md`, `PRODUCT.md` (Positioning, principles 2 and 4), `DESIGN.md` (Honesty visuals, The One Alarm Rule). Prior phases: 66 (primitive UI), 118 (charts), 123/132 (PriorityView, turn surfacing, `open_items`), 107 (workflow failure policy), 170 (stuck goals from the earliest fired gate), 177 (notifications through the governor), 181 (held writes).

**Depends on**: nothing unfinished. Runs in parallel with 183 (W1). Must land before 187 (W3).

**Doctrine functions served**: executive function (what slipped, what waits on the user) and governance (every claim shows its posture; unattended failures are explained in plain words and reachable from the notification that reports them).

---

## Overview

The Jarvis prototype answers "What's slipping?", "How is X going?" and "What should I decide today?" by composing HUD modules in the browser from six REST calls (`pages/jarvis/model/compose.ts`). The user decided the canvas must render what the backend emits instead (decision 7). Today the backend cannot: server-driven components (`ze-components`) are generic layout primitives written by the model through `render_*` tools, with no field for a claim's kind, confidence, source or age. The only claim-bearing component the engine emits, the inline "Still open" list from `surface_loops`, is a raw dict (`type: "open_items"`) outside the primitive schema that ze-web silently drops.

This phase adds four things and fixes one:

1. **Claim posture on descriptors (gap 2).** A `ClaimPosture` sub-type (kind, subject, reference, confidence, decayed-from value, source, as-of time, state, slipped) on every primitive, set only by code from the owning record, never by the model.
2. **Composed answers (gap 1).** Three claim-bearing primitives (`headline`, `claim_card`, `claim_timeline`) and a `WorldComposer` in `ze-priority` that builds the three answers from the stores. A preset chip sends an explicit `compose` intent and gets the composition deterministically; a typed question can reach the same composer through three companion tools. The model writes only the sentence, grounded in the composer's summary.
3. **Workflow failure line (gap 9).** A plain-language `failure_summary` on every failed execution, derived by a pure function, never raw exception text.
4. **Goal progress on the list (gap 10).** `listGoals` rows carry milestones done/total, the next milestone, the open gate and whether the goal is stuck.
5. **Notification deep links (gap 14).** Notifications already carry `target_type`/`target_id`, but the workflow failure push points at the workflow, not the execution, and a gate's goal is not reachable from the gate id. This phase adds `target_parent_id` and corrects the targets.

## Clarifications

### Session 2026-10-17 (Spec Architect, from the code)

- Notification targets already exist (`notifications.target_type`, `target_id`, zpro002); gap 14 is narrower than the plan states. The workflow failure push sends `target_type="workflow_run"` with the **workflow** id; it becomes `workflow_execution` with the execution id and the workflow as parent.
- Goal gates have no due date (`goal_gates` has `fired_at`, `resolved_at`). The plan's `gate_due_at` is replaced by `gate_open_since` (the gate's `fired_at`) so the field says what is true.
- `surface_loops` emits `{"type": "open_items", …}`, which is not a primitive and which ze-web never renders. It is replaced by claim cards (hard cut).

### Session 2026-10-17 (Floor Reviewer Gauge, changes applied)

- `preset_components` is reset in `make_graph_input`; the preset reaches tools through a new `AgentContext.preset` (fetch_context's `extensions` never reach the agent); the compound path returns the preset components itself; `WsScreenContext` gains `compose`/`topic`; a retry answers from normal routing; the compose tools register through `ze_priority._AGENT_MODULE_PATHS`; failure lines say "after step k" when steps ran; the eval API gains `context`; `kind` is null for workflow and held-write subjects; OQ-1 is split and OQ-2 is a confirmation.

### Open questions for the user (Spec Architect's recommendation in bold; tasks follow the recommendation)

- OQ-1a: Does a preset chip send an explicit intent? → **Recommended: yes. The chip sends its text with `context.compose` (`slipping` | `decisions` | `topic` + `topic`); the engine routes that turn to companion, runs the composer before the agent, and the model writes the sentence from the composer's summary.** Alternative: rely on routing alone (needs new routing criteria and a live `make calibrate-routing` re-run, which costs credits, and "what am I still sitting with?" routes to the loops agent today). Alternative: answer presets with no model call at all (no sentence in Ze's voice).
- OQ-1b: May a typed question reach the same composer? → **Recommended: yes, through three READ tools on companion (`show_slipping`, `show_decisions`, `show_topic`) when routing gives companion the turn.** Alternative: presets only; typed questions answer as today. (Independent of OQ-1a; the user may accept one and not the other.)
- OQ-2 (confirmation, not a choice): posture is set only by code from the owning record; the `claim` field is excluded from every `render_*` schema and stripped if the model sends it. This follows `specs/arch/claim-topology.md` (a model-written confidence is a fabricated claim). Deferred, not proposed: letting the model pass a reference (`subject`, `id`) that the server resolves to posture.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - "What's slipping?" answers with real modules (Priority: P1)

The user taps the "What's slipping?" preset. The reply carries a dot-matrix headline ("2 SLIPPING · 1 AT RISK"), a timeline of concerns from seven days ago to seven days ahead, one card per slipped or at-risk item (a drifting loop, a stuck goal), and, when a stale follow-up is ranked, one person card. Each card carries the posture of its record: kind, confidence, source, age, state, and `slipped` for drifting loops and stuck goals. Ze's sentence names what slipped and offers one next step, using only what the composition contains.

**Why this priority**: It is the demo moment of the overhaul and the first thing W3 renders.

**Independent Test**: With fake stores (two drifting loops, one active loop due in three days, one stuck goal, one suspected loop), call `WorldComposer.compose_slipping()`: the headline reads `3 SLIPPING · 1 AT RISK`; the timeline has three entries (the three loops; goals are cards, not timeline entries); there are four cards with `slipped` true on the three slipped ones; the suspected loop is absent; every card's `claim` equals the store values. Through the graph with `context.compose = "slipping"`: the turn is routed to companion, `components` starts with the composition, and the composer is not called again by a tool.

**Acceptance Scenarios**:

1. **Given** nothing drifting, no stuck goal and nothing due within 7 days, **When** the composition runs, **Then** the headline reads `NOTHING SLIPPING`, there are no cards, and the summary tells the model how many concerns Ze is watching.
2. **Given** the priority source for hypotheses fails, **When** the composition runs, **Then** it renders from the sources that succeeded and the summary and composition list `sources_failed`.
3. **Given** a drifting loop, **When** its card is built, **Then** `tone` is `hot`, `claim.slipped` is true, and `claim.state` is `drifting`; an active loop due in 3 days is `default` tone with a readout "due in 3 d".

---

### User Story 2 - "What should I decide today?" lists only what needs the user (Priority: P1)

The reply lists open held writes (cream, Approve / Deny), goals waiting at a gate (cream, Approve / Open), and suspected loops (dashed frame, "Yes, track it" / Drop), with the headline "N TO DECIDE". Each action carries a closed intent and the record id, so the client can execute it with the call it already has.

**Why this priority**: Attention is scarce (principle 3); decisions are what Ze cannot do alone.

**Independent Test**: Fake stores with one open held write, one goal awaiting a gate, two suspected loops: `compose_decisions()` returns the headline `4 TO DECIDE`, four cards in that order, the actions `approve_held_write`/`deny_held_write`, `approve_gate`/`open`, `confirm_loop`/`drop_loop` with the right ids, `tone` cream for held write and gate and dotted for suspicions (never hot).

**Acceptance Scenarios**:

1. **Given** nothing to decide, **When** composed, **Then** the headline reads `NOTHING TO DECIDE` and the summary says so.
2. **Given** an expired held write, **When** composed, **Then** it is absent.

---

### User Story 3 - "How is X going?" gathers one topic across stores (Priority: P2)

The user asks about a project. The composer matches the topic against open loops, displayed goals, workflows and ranked hypotheses, and returns their cards with posture (a hypothesis is `inference` or `suspicion`, shown dotted), goal progress, workflow last result, and a headline `<TOPIC> · N SLIPPED · M WORKFLOWS`. Nothing matching → headline `NOTHING ON <TOPIC>` and a summary that says Ze holds nothing open about it.

**Why this priority**: Valuable, but the matching floor is uncalibrated; slipping and decisions come first.

**Independent Test**: With a fake embedder returning fixed vectors, `compose_topic("ledgerlite launch")` returns exactly the items whose title cosine is ≥ the floor, ordered loops, goals, workflows, hypotheses; each list capped at 6.

**Acceptance Scenarios**:

1. **Given** a topic longer than the headline allows, **When** composed, **Then** the headline topic is uppercased, reduced to the DotMatrix glyph set, and truncated to fit 40 characters.
2. **Given** typed text "how is the LedgerLite launch going?" routed to companion, **When** the model calls `show_topic`, **Then** the same composition is appended to the reply's components and the tool returns the summary.

---

### User Story 4 - Posture is never authored by the model (Priority: P1)

Every primitive type may carry `claim`, but no `render_*` tool schema exposes it, and a `claim` argument from the model is dropped with a warning. Only code that reads the owning record sets it.

**Why this priority**: The whole point of posture is honesty; a model-authored confidence is a fabricated claim.

**Independent Test**: For every registered `render_*` tool, the JSON schema contains no `claim` key at any depth. Calling a render tool with `claim={...}` produces a component without `claim` and logs `render_tool_claim_dropped`.

**Acceptance Scenarios**:

1. **Given** `export_json_schema()`, **When** generated, **Then** `ClaimPosture` is in `$defs` and every primitive has an optional `claim` property.
2. **Given** the inline open-items mention on a normal turn, **When** `surface_loops` runs, **Then** it appends claim cards built from the loop/goal records (no `open_items` dict exists anywhere).

---

### User Story 5 - A failed workflow run says why in one plain line (Priority: P1)

Every failed execution carries `failure_summary`, for example: "Step 2 of 4, “Check the inbox”, failed: it ran out of time after 3 attempts." It never contains exception text or tracebacks. REST, the workflow agent's tools and the failure push use it.

**Why this priority**: The current UI shows raw error strings; DESIGN.md forbids raw tracebacks.

**Independent Test**: Table test of the pure function over executions: timeout, cancellation, declined write, deletion while held, spend budget pause, unknown error, failure before the first step, multi-attempt, success (→ `None`). No output contains the raw `error` text.

**Acceptance Scenarios**:

1. **Given** a completed execution, **When** serialized, **Then** `failure_summary` is `null`.
2. **Given** a failed execution, **When** the failure push is sent, **Then** its body is the failure summary and it targets `workflow_execution` with the workflow as parent.

---

### User Story 6 - Goal rows show progress without a second call (Priority: P1)

`GET /api/v0/goals` rows carry `milestones_done`, `milestones_total`, `next_milestone`, `gate_id`, `gate_title`, `gate_open_since`, `last_progress_at` and `stuck_since` (null unless the goal is stuck by the same rule the stuck-goal job uses).

**Why this priority**: Doing (W4) and the composer need progress on every row.

**Independent Test**: Store test with a fake pool returning goals with mixed milestone states and one fired open gate; REST test checks the fields and that one SQL round trip serves the list (no N+1).

**Acceptance Scenarios**:

1. **Given** a goal with 2 of 5 milestones completed or skipped, **When** listed, **Then** `milestones_done` is 2, `milestones_total` 5, `next_milestone` is the lowest-sequence pending or in-progress milestone title.
2. **Given** an active goal with no progress for 7 days, **When** listed, **Then** `stuck_since` is the last progress time; for a goal awaiting a gate fired 7+ days ago, `stuck_since` is the gate's `fired_at`.

---

### User Story 7 - A notification opens the exact thing it reports (Priority: P2)

Notification rows and `notification` WS frames carry `target_type`, `target_id` and a new `target_parent_id`, so a client can open the execution inside its workflow or the gate inside its goal.

**Why this priority**: "While you were away" needs one action per row (W2); the data is mostly there.

**Independent Test**: Notifier test: `notify(..., target_parent_id=…)` persists and returns it in `list_page` and in the WS frame. Workflow failure handler test: target is `workflow_execution` / execution id / parent workflow id. Gate push test: target `goal_gate` / gate id / parent goal id.

**Acceptance Scenarios**:

1. **Given** `target_type="workflow_run"` anywhere in the code, **When** searched, **Then** it does not exist.
2. **Given** a notification without a parent, **When** listed, **Then** `target_parent_id` is null.

---

### Edge Cases

- A composition source raises: the composer drops that source, records it in `sources_failed`, and still returns; only when every source fails does it return an empty composition with headline `COULD NOT READ THE WORLD` and a summary telling the model to say so.
- `context.compose` with an unknown value or with `topic` missing for `topic`: ignored (normal routing), warning logged.
- `context.compose` on a compound turn or a forced (eval) route: the composition still runs and is prepended; routing is not changed for forced routes.
- A retry (phase 165/180) of a preset turn answers from normal routing: the retry path (`api/ws/turns.py` retry `config_extra`) carries no `screen_context`, and the user message does not store its context, so no composition is prepended. This is the same pre-existing gap as workflow screen context on retry; persisting message context is out of scope. A test pins the behaviour.
- Headline text: only `A–Z 0–9 · : -` and space (the DotMatrix glyph set); anything else is removed; max 40 characters.
- Topic matching uses the E5 passage embedder already in the container; with no embedder the topic composition returns empty with a summary saying matching is unavailable.
- Notification dedup (`exists_recent`) keeps keying on `(event_type, target_type, target_id)`; the parent is not part of the key.

## Requirements *(mandatory)*

### Functional Requirements

**Claim posture (gap 2)**

- **FR-001**: `ze-components` MUST define `ClaimPosture` (`kind`: the seven `ClaimKind` values, or null for `workflow` and `held_write` subjects, which are not claims; `subject`: `loop` | `goal` | `workflow` | `hypothesis` | `person` | `held_write` | `fact`; `ref_id`; optional `confidence`, `confidence_from`, `source`, `as_of` (ISO 8601), `state`, and `slipped` default false) and register it in `PRIMITIVE_SUB_TYPES`. `state` values per subject are listed in the contract (`contracts/claim-descriptors.md`).
- **FR-002**: Every class in `PRIMITIVE_TYPES` MUST gain `claim: ClaimPosture | None = None`.
- **FR-003**: `build_render_schema` MUST omit `claim` at every depth, and the `render_tool` wrapper MUST drop a `claim` argument and log `render_tool_claim_dropped`. Every existing `render_*` schema is otherwise unchanged.
- **FR-004**: `confidence_from` is set only when the owning record exposes the value it decayed from; until phase 185 (B2, gap 4) adds it for loops, loop cards omit it (DESIGN.md "a value the API does not expose is omitted, not faked").

**Composed answers (gap 1)**

- **FR-005**: `ze-components` MUST add three primitives: `Headline` (`text`), `ClaimCard` (`title`, required `claim`, `span` 4 | 6 | 8 | 12, `lines`, `readouts` of `Readout{label, value, tone}`, optional `progress_done`/`progress_total`, `actions` of `CardAction{label, intent, ref_id}`, `tone` default | cream | hot | dotted) and `ClaimTimeline` (`title`, `entries` of `TimelineEntry{title, claim, due_at}`, `days_before`, `days_after`, `span`). `CardAction.intent` is closed: `confirm_loop`, `drop_loop`, `approve_held_write`, `deny_held_write`, `approve_gate`, `open`. None of the three has a `render_*` tool.
- **FR-006**: Tone MUST follow DESIGN.md: `hot` only when `claim.slipped` (drifting loop, stuck goal, failed workflow); `cream` for a card that needs the user (held write, gate); `dotted` for `suspicion` or `inference` posture that is not slipped; otherwise `default`.
- **FR-007**: `ze-priority` MUST add `WorldComposer` (`ze_priority/compose/`) with `compose_slipping()`, `compose_decisions()`, `compose_topic(topic)`, each returning a `Composition` (`headline`, `components` as serialized primitives, `summary` as a short factual text for the model, `sources_failed`). Its inputs are `PriorityView`, the loop store, the goal store (FR-016 progress method), the workflow store and the held-write store, all injected. The composition rules are in `contracts/composition-rules.md`; they are pure functions over fetched records, unit-tested without I/O.
- **FR-008**: The `message` frame MUST accept `context.compose` (`slipping` | `decisions` | `topic`) and `context.topic` (≤ 120 chars): `WsScreenContext` in `api/ws/schemas.py` gains both fields, the generated WS types are regenerated, and `tests/api/test_ws_conformance.py` covers them. When present and valid, `fetch_context` routes the turn to companion (unless forced or compound), calls the composer through `config["configurable"]["world_composer"]`, stores the components in a new `AgentState.preset_components`, sets `AgentContext.preset` (new field) to the preset key (`slipping`, `decisions`, or `topic:<normalized topic>`), and injects the summary as a system note ("[Composed answer — write one or two sentences from this only: …]"). `preset_components` MUST be reset to `[]` in `make_graph_input` (`ze_core/conversation/turn.py`) like every per-turn key, so a checkpointed thread never carries a preset into the next turn. The execution node prepends `preset_components` on the single-agent path (where it sets `components` from `pop_components`), and on the compound path, which returns no `components` key today, it returns `components = preset_components`. Both `AgentContext` constructors in `nodes/execution.py` pass `preset` through (next to the prompt-note kwargs).
- **FR-009**: `ze-priority` MUST register three READ tools, `show_slipping()`, `show_decisions()`, `show_topic(topic)`, in `ze_priority/compose/tools.py`, added to `ze_priority._AGENT_MODULE_PATHS` (imported by `import_agent_modules()` before agents bootstrap). Each takes injected `world_composer` and `preset: str | None`; it calls the composer and returns `{"summary", "sources_failed"}`, and appends the components through `ze_components.context.append` unless `preset` equals its own key exactly (the turn already shows them; topic keys carry the normalized topic). Companion lists the tool names, receives `world_composer` through its constructor, and passes `{**self.tool_deps(), "preset": ctx.preset}` as `deps` in `run()` (no `BaseAgent.tool_deps` signature change); its instructions say when to call them and to ground the sentence in the summary only.
- **FR-010**: `surface_loops` MUST build its inline mention component from claim cards produced by a new `TurnSurfacing.mention_cards(mentions)` (posture from the loop/goal records). The `open_items` dict and `_build_component` in `loop_surfacing.py` are deleted. The text section appended to `final_response` is unchanged.
- **FR-011**: `describe_components` MUST name the new types ("a headline", "a card", "a timeline") for history and push bodies.

**Workflow failure line (gap 9)**

- **FR-012**: `ze_automation/workflow/failure.py` MUST provide a pure `failure_summary(execution) -> str | None` following `contracts/failure-summary.md`. It never includes the raw `error` text.
- **FR-013**: `failure_summary` MUST appear on `WorkflowExecutionResponse` (list and detail), in the workflow agent's execution serializer, and as the body of the workflow failure push (replacing `execution.summary or str(exc)`). `error` stays on the REST response as the raw detail; clients do not render it as the primary line.

**Goal progress (gap 10)**

- **FR-014**: `GoalListItem` MUST gain `milestones_done`, `milestones_total`, `next_milestone`, `gate_id`, `gate_title`, `gate_open_since`, `last_progress_at`, `stuck_since`.
- **FR-015**: `stuck_since` MUST use the stuck-goal job's staleness rule with one shared constant `STUCK_IDLE_DAYS = 7` in `ze_automation.goals`, replacing the literal in `jobs/stuck_goals.py`: for an active goal the reference time is the last completed or skipped milestone, else `created_at`, and `stuck_since` = that reference when `is_stale(reference, STUCK_IDLE_DAYS)`; for a goal awaiting a gate it is the earliest fired open gate's `fired_at` when stale. `last_progress_at` stays null when no milestone completed. The job's `last_stuck_alert_at` cooldown is push pacing and is ignored for display.
- **FR-016**: `PostgresGoalStore.list_progress()` MUST return `list[GoalProgress]` for the statuses `list_for_display` returns, in one query (aggregates over `goal_milestones`, a lateral pick of the next milestone and the earliest fired open gate). `list_for_display` (its only caller is `listGoals`) is deleted from `PostgresGoalStore` and the `GoalStore` Protocol; `list_progress` joins the Protocol.

**Notification deep links (gap 14)**

- **FR-017**: Migration `zpro005` MUST add `notifications.target_parent_id TEXT NULL`. `NotificationRow`, `Notification`, the store's create/list, `ProactiveNotifier.notify`/`_notify`, held release, the `notification` WS frame, `NotificationItem` and the generated client MUST carry it.
- **FR-018**: Callers MUST set targets per `contracts/notification-targets.md`: workflow failure → `workflow_execution` / execution id / parent workflow id; goal gate → `goal_gate` / gate id / parent goal id. `workflow_run` is removed.

**Web (interim, kept minimal)**

- **FR-019**: `make codegen` MUST regenerate `@myguyze/ze-ui` and `@myguyze/ze-client`. `PrimitiveRenderer` MUST render the three new primitives minimally (headline as text, card as title + lines + readouts + actions, timeline as an ordered list) so the current chat shows them until W3 restyles them; card actions dispatch to the existing loop, held-write and gate calls.
- **FR-020**: ze-web MUST show `failure_summary` instead of the raw error in the workflow executions widget and show progress fields on goal rows. Notification links: phase 183 owns `notificationHref` (built from this phase's target table, with `target_parent_id` optional); this phase only adds `target_parent_id` to the generated type and extends that function's table tests. If 184 lands before 183, the JR lane implements `notificationHref` in the current `notification-format.ts` instead and 183 re-points it.

### Key Entities

- **ClaimPosture**: the visible posture of one claim: kind, subject, reference, confidence (and the value it decayed from when known), source, as-of time, state, slipped.
- **Composition**: headline + components + summary + sources_failed. Not persisted; stored only as the reply's components.
- **GoalProgress**: goal + milestone counts + next milestone + open gate + last progress + stuck since. Not persisted.
- **Notification target**: `target_type`, `target_id`, `target_parent_id`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the three presets on seeded dev data (`make dev`), every card's posture matches the database row it came from (spot check of 10 cards, recorded in the Handoffs note).
- **SC-002**: No `render_*` schema contains `claim`; no `open_items` component dict remains (the `open_items_query` state flag stays); `git grep -nE '(^|[^_a-z])"workflow_run"|target_type="workflow_run"' -- core apps plugins packages` returns nothing (the unrelated `cancel_workflow_run` tool and the prototype's `event_type` check in `pages/jarvis/model/world.ts` are not targets).
- **SC-003**: 0 failed executions in the dev database have a `failure_summary` containing their raw `error` text.
- **SC-004**: `listGoals` serves N goals in one SQL statement (asserted by the fake pool call count).
- **SC-005**: The new eval scenarios (`eval/scenarios/composed_answers.yaml`, EN and PT) pass with the judge; the sentence names only items present in the composition.
- **SC-006**: `make test-py`, `make test-pg` (goal progress and notification migration), `make test-web`, `make typecheck-web`, `make lint` pass.

## Assumptions

- The three presets' text and topic come from the client (phase 187 decides the "How is X going?" topic, for example the top-ranked goal's title).
- The composer's caps (6 cards per list, 12 per composition) and the 7-day windows are product constants, not calibrated bars.
- The topic match floor reuses `ze_priority.tools._MATCH_FLOOR` (0.55, E5 cosine), uncalibrated like the `reprioritize_item` match it shares; calibrating it is out of scope (noted in research for a later System One question).

## Out of Scope

- Hypotheses as a REST list, loop `confidence_at_last_evidence`, budget remaining, reminders over REST (phase 185, B2).
- Model-authored posture or reference resolution (OQ-2).
- The visual design of the new primitives (phase 187, W3); this phase renders them minimally.
- Changing routing criteria or calibration sets.

## Verbatim Constraints

- "B1 (composed answers + posture on descriptors, gaps 1, 2, 9, 10, 14) runs before W3; W3 does not ship client-side compositions." (user decision 7, 2026-10-17)
- "Ze is not an agenda or notes app; every view answers 'what does Ze understand, and what is it doing about it?'" (user, via the Maestro, 2026-10-17)
