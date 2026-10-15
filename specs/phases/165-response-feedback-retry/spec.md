# Feature Specification: Assistant Response Feedback and Retry

**Feature Branch**: `165-response-feedback-retry`

**Created**: 2026-10-09

**Status**: Implemented

**Input**: User description: "Each assistant reply offers thumbs up, thumbs down and Retry on hover/focus. Retry is allowed only when the turn was text-only or every action it took can be rolled back; it regenerates the reply and never re-executes side effects. Feedback is evidence, not a user fact: modeled with the contribution-seam vocabulary close to the Phase 135 action-record ledger. Capture only in v1 (no learning consumer, no procedure promotion): link each feedback item to that message's `MessageTrace` so the routing envelope, System One judgments (163, 164), memory used and tools run are reconstructable. Feedback is visible in the trace panel next to the message's trace."

**Governed by**: [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md), [`specs/arch/claim-topology.md`](../../arch/claim-topology.md), [`specs/arch/system-one-models.md`](../../arch/system-one-models.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md).

**Depends on**: Phase 135 (action-record ledger — the evidence-ledger pattern this phase copies), 136 (action instrumentation), 152 (per-delegate confirmation), 163 and 164 (System One judgments on the trace), 89 and 90 (message trace and trace panel). Split out of Phase [117](../117-web-hig-fixes/spec.md) US9.

**Does not start**: undo-then-regenerate (deferred, below), any consumer of feedback (calibration, routing or admission tuning, procedure promotion, ranking), automatic rollback of side effects, free-text feedback, feedback on user messages.

---

## Overview

Ze shows an assistant reply and nothing more. The person cannot say "this was good", "this was wrong", or "try again", and Ze gets no labeled signal about which of its judgments led to a good or bad reply. Phases 163 and 164 put typed System One judgments on every `MessageTrace`; without a human label next to that trace, nobody can later check those judgments against what the person thought of the result.

This phase adds two things.

1. **Feedback capture.** Each assistant reply gets thumbs up and thumbs down. A rating is stored as **evidence about the reply**, never as a fact about the user. It is an append-only record in the same family as the Phase 135 `ActionRecord` ledger: it cites the authoritative message, carries doctrine provenance and confidence, and links to that message's `MessageTrace`. Nothing reads it back into a turn in v1.
2. **Safe Retry.** Each assistant reply also gets Retry, which regenerates the reply for the same user message. Retry is offered only when it cannot repeat or duplicate a side effect. When the original turn did something Retry cannot safely redo, Retry is unavailable and says why. Retry regenerates text; it never re-executes tools that write.

The value is labeled data for later work. This phase builds the labeled dataset and the places a person can see it, and nothing that consumes it.

### Evidence, not a fact

A thumb is an observation of the user's reaction to Ze's output. It is not "the user prefers X", and it must not enter `memory_facts`, fact embeddings, retrieval, user-profile synthesis, contradiction detection, or the memory feed. Like an `ActionRecord`, it is operational evidence that later phases may cite. Ze never says "you liked that" on the strength of a thumb.

## Clarifications

### Session 2026-10-09

The user pinned scope before drafting (UI, retry safety, feedback-as-evidence, capture-only, visible in trace panel), then answered three questions raised by code review.

- Q: Rollback. Does v1 build an undo-then-regenerate executor? → A: No. v1 is text-only retry. A turn with any reversible action shows Retry unavailable, with a reason naming the action. Automatic undo-then-regenerate is wanted later and is recorded as deferred future work (its own phase, see "Deferred: Undo-then-Regenerate"). The reversibility declaration on WRITE tools is designed now to support it.
- Q: Doctrine placement. → A: New closed `ClaimKind.FEEDBACK_RECORD`, licensed only to `SourceFunction.PERCEPTION` (alongside `FACT`), in a `ze-memory`-owned append-only `feedback_records` table (`zm024`).
- Q: Passive memory extraction. → A: Post-reply fact admission does not block Retry. The retry run skips admission entirely.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Rate a reply (Priority: P1)

A person reads an assistant reply and hovers over it, or tabs to it. Thumbs up and thumbs down appear. They press one. The control shows their choice immediately and keeps showing it after a reload. They can press the same thumb again to clear it, or press the other thumb to change it.

**Why this priority**: This is the labeled signal. Without it nothing else in the phase has a purpose.

**Independent Test**: In the web app, send a message, hover the reply, press thumbs down, reload the page. The reply still shows thumbs down. Press it again; the reply shows no rating.

**Acceptance Scenarios**:

1. **Given** a delivered assistant reply, **When** the person hovers or focuses it, **Then** thumbs up, thumbs down and Retry controls appear, each with an accessible name, reachable by keyboard.
2. **Given** a reply with no rating, **When** the person presses thumbs up, **Then** the control shows a pressed state at once and a feedback record is stored for that message.
3. **Given** a reply rated thumbs up, **When** the person presses thumbs down, **Then** the current rating becomes thumbs down and the earlier rating is kept as history, not overwritten.
4. **Given** a rated reply, **When** the person presses the active thumb again, **Then** the current rating is cleared and the clear is itself kept as history.
5. **Given** a rated reply, **When** the page reloads or the thread is reopened on another device, **Then** the rating still shows.
6. **Given** a touch device with no hover, **When** the person views a reply, **Then** the controls are reachable without hover (focus or tap).
7. **Given** the save fails (network or server error), **When** the person presses a thumb, **Then** the control reverts and shows a short, non-blocking error; no half-saved state remains.

---

### User Story 2 - Feedback is reconstructable evidence tied to the trace (Priority: P1)

Later, someone (or a future phase) looks at a thumbs-down and wants to know why the reply was bad: how it was routed, what System One judged, what memory it used, and which tools ran. Every feedback record points at its message, and that message's trace answers those questions.

**Why this priority**: The pin's whole goal is labeled training data. A rating without the trace behind it is noise.

**Independent Test**: Rate a reply produced by a routed turn that had System One judgments, memory chunks and a tool call. Read the feedback record and its linked trace. Confirm the routing envelope, every judgment row, memory chunks, and tool calls are all reachable from the record without any other lookup key than the message id.

**Acceptance Scenarios**:

1. **Given** a rating on a reply, **When** the record is read back, **Then** it carries the message id, thread id, rating, who rated (the single user), when, and provenance/confidence from the shared claim vocabulary.
2. **Given** that message has a `MessageTrace`, **When** the feedback record is resolved, **Then** the routing envelope, `judgments` (163 speech-act, 164 routing choice and complexity), `memory_chunks`, `tool_calls`, `skills_used`, `conductor_ledger`, and `compaction` data from the trace are reachable through the message id.
3. **Given** an assistant message with no recorded trace (a command reply, a pre-Phase-89 message, a proactive push), **When** it is rated, **Then** the rating is still stored and marked as having no trace; nothing is invented.
4. **Given** a feedback record, **When** anything reads user memory (retrieval, profile, memory feed, fact review), **Then** it never appears there, and no `memory_facts` row is written.
5. **Given** feedback exists, **When** any conversation turn runs, **Then** no part of Ze's routing, admission, prompts or ranking reads it (capture only).

---

### User Story 3 - Retry a text-only reply (Priority: P1)

A person gets a reply they dislike, and the turn only produced text (including turns that only read: lookups, search, memory recall, calendar reads). They press Retry. Ze regenerates the reply for the same user message. The new reply takes the old one's place in the conversation. The old one is kept as evidence, hidden from the thread by default, and its feedback stays attached to it.

**Why this priority**: Retry is the second half of the pinned UI and it is the safe, common case.

**Independent Test**: Send a question that routes to research and uses only read tools. Press Retry. A new reply appears for the same question, the old reply is no longer shown in the thread, and no write tool ran during the regeneration (verified through the new trace).

**Acceptance Scenarios**:

1. **Given** a delivered reply whose turn ran no write tool and no confirmed gate, **When** the person presses Retry, **Then** Ze regenerates the reply from the same user message and thread context, with the original reply and anything after it excluded from context.
2. **Given** a retry run, **When** it executes, **Then** every write-access tool is blocked for that run and memory admission is skipped; if the model wants to write, the reply says so in words and offers to do it as a normal request.
3. **Given** a completed retry, **When** the thread renders, **Then** the new reply replaces the old one in place, the old reply stays stored with a link to its replacement, and the new reply has its own trace and its own (empty) feedback.
4. **Given** a reply that already has a rating, **When** the person retries it, **Then** the old reply keeps its rating, and the retry itself is recorded as evidence linked to the old message (an implicit negative signal that is distinguishable from a thumb).
5. **Given** a retry is running, **When** the person presses Retry again or sends a new message, **Then** the duplicate Retry is refused with the existing "busy" behavior and no second regeneration starts.
6. **Given** a retry fails (model error, timeout), **When** it ends, **Then** the original reply remains shown, unchanged, with a visible failure notice; no half-replaced thread.

---

### User Story 4 - Retry explains when it is unsafe (Priority: P1)

A person tries to retry a reply from a turn that did something: set a reminder, created a goal, ran a workspace command, sent an email, or approved a confirmation. Retry does not rerun any of it. Instead the control is disabled and tells them what the turn did and why it cannot be repeated.

**Why this priority**: Without this, Retry is a way to send a duplicate email. Safety is the pin's core constraint.

**Independent Test**: For each of: a reminder created, a goal created, a workflow created, a workspace run, an email sent, a calendar event created, a confirmation approved — produce the turn, open Retry, and confirm it is unavailable with the right reason and that pressing it cannot start a run (including by calling the interface directly).

**Acceptance Scenarios**:

1. **Given** a turn whose tool calls include any write-access tool that ran (success or failure, because a failure may have partly executed), **When** Retry is evaluated, **Then** it is unavailable and the reason names the action in plain words (for example "This reply set a reminder").
2. **Given** a turn that ran only reversible actions (reminder, open loop, goal, workflow, a fact the user asked Ze to remember), **When** Retry is evaluated, **Then** it is still unavailable in v1 (see Deferred), and the reason says the action can be undone separately.
3. **Given** a turn with any irreversible action (outbound message or email, outreach, workspace command, calendar invite sent to others, ingestion), **When** Retry is evaluated, **Then** it is unavailable and the reason says the action cannot be undone.
4. **Given** a turn where a per-delegate confirmation (Phase 152) was approved and the write ran, **When** Retry is evaluated, **Then** it counts as an action taken. A confirmation that was denied, timed out, or is still pending counts as no action.
5. **Given** a turn that paused at a confirmation and has no final reply, **When** the thread renders, **Then** no Retry control appears for it (nothing to regenerate yet).
6. **Given** a turn whose side effects cannot be determined (trace missing, tool unknown to the registry, tool reversibility undeclared), **When** Retry is evaluated, **Then** Retry is unavailable ("Ze cannot tell what this reply did"). Unknown never means safe.
7. **Given** any client (including a hand-built request), **When** it asks the server to retry an ineligible reply, **Then** the server refuses with the same reason. Eligibility is decided on the server, not trusted from the UI.
8. **Given** the unavailable control, **When** the person hovers, focuses or taps it, **Then** the reason is readable by keyboard and screen reader, not only in a tooltip.

---

### User Story 5 - See feedback in the trace panel (Priority: P2)

A person opens the trace panel for a message. Next to routing, memory, tools and judgments they see the feedback on that reply: current rating, when it was given, the history of changes, whether the reply was retried, and, if so, a link to the replacement.

**Why this priority**: Makes the captured data inspectable in v1 without a new page. Rating and Retry work without it.

**Independent Test**: Rate a reply, change the rating, retry another. Open each in the trace panel and confirm the feedback section shows current rating, history, and the retry link.

**Acceptance Scenarios**:

1. **Given** a message with feedback, **When** its trace entry renders, **Then** a Feedback section shows the current rating and each earlier change with time.
2. **Given** a message with no feedback, **When** its trace entry renders, **Then** the section is absent or reads "No feedback yet"; it never shows a fabricated value.
3. **Given** a message that was retried, **When** its trace entry renders, **Then** it shows "Retried" with a link to the replacement and the replacement's trace shows "Replaces an earlier reply".
4. **Given** a rating is saved while the panel is open, **When** it succeeds, **Then** the panel updates without a reload.
5. **Given** a message with no trace, **When** it has feedback, **Then** feedback is still reachable where the panel lists that message, marked "no trace recorded".

---

### Edge Cases

- A reply is rated, then the thread is deleted or the user data is deleted/exported: feedback follows the same delete and export paths as messages (Data domain); no orphan rows.
- Two quick presses (thumb then other thumb) resolve in order; the final stored current rating matches the last press; history holds both.
- Rating an old reply in a long thread: allowed for any delivered assistant message. Retry is allowed only on the **latest** assistant reply of a thread (older retries would rewrite history that later turns depended on); older replies show Retry unavailable with that reason.
- Command replies (`/status`, `/reset`), proactive pushes and pre-Phase-89 messages are stored assistant messages with no trace. They get thumbs (rating is still evidence) and Retry is unavailable (`trace_unavailable`). Confirmation prompts, progress and typing frames are not stored messages and get no controls.
- A compound or conductor turn with several subtasks or delegates: eligibility looks at all of them; one write anywhere blocks Retry.
- A turn that used a workspace run still in progress (Phase 116, 129): counts as an irreversible action.
- A retried reply is itself retryable and rateable (new message, new trace). Each retry supersedes the one before; the chain is kept.
- The trace is missing a field the eligibility rule needs: unavailable (see US4-6).
- Feedback arrives for a message id that does not exist or is a user message: rejected as not found/invalid, nothing stored.
- The WebSocket is down: thumbs use the REST path and still work. Retry needs the live turn path; with no socket the control is disabled with a "reconnecting" reason.
- Retry run hits a confirmation gate: cannot occur, because writes are blocked; reads never gate.

## Requirements *(mandatory)*

### Functional Requirements

**Feedback capture**

- **FR-001**: The system MUST let the person set thumbs up or thumbs down on any delivered assistant message, change it, and clear it.
- **FR-002**: Every rating change MUST append one immutable feedback record. The current rating is the latest record for that message. Records are never updated or deleted by ordinary operation.
- **FR-003**: Setting a rating MUST be idempotent: repeating the same logical action (same message, same resulting state, same client idempotency key) MUST NOT append a duplicate.
- **FR-004**: A feedback record MUST include: stable id, idempotency key, message id, thread id, kind (`thumbs_up`, `thumbs_down`, `cleared`, `retry_requested`), occurred-at, provenance and confidence from the shared claim vocabulary (user-stated, full confidence), source function, claim kind, and whether the message had a trace when rated.
- **FR-005**: A feedback record MUST be submitted through the contribution seam as a new closed claim kind licensed to a single source function (Perception, per Clarifications), validated by `validate_and_submit`. It MUST NOT be a `Fact`, `Signal`, `OpenLoop`, or `ActionRecord`.
- **FR-006**: Feedback MUST NOT write to `memory_facts`, fact embeddings, user-profile synthesis, retrieval, contradiction detection, the memory feed, or fact review.
- **FR-007**: No conversation turn, router, System One question, extractor, ranker or prompt MAY read feedback in this phase. (Capture only.) A test MUST fail if any such read path is added.
- **FR-008**: Each feedback record MUST be linked to the message's `MessageTrace` by message id such that routing envelope, `judgments`, `memory_chunks`, `tool_calls`, `skills_used`, `conductor_ledger` and `compaction` are reachable from the record. The trace is not copied into the feedback record.
- **FR-009**: The trace of a message that has feedback MUST NOT be rewritten or dropped while the feedback exists (the link would break). Trace retention is unchanged for messages without feedback.
- **FR-010**: Feedback MUST NOT contain free text or any message content. v1 stores the enumerated kind only.

**Retry**

- **FR-011**: Retry MUST regenerate the assistant reply for the user message that produced it, using the thread context as it was before the original reply.
- **FR-012**: Retry MUST be allowed only for the latest assistant reply of a thread, and only when the original turn is *retry-safe*: every tool call that ran was a read-access tool, no per-delegate confirmation (Phase 152) was approved and executed, no workspace run started, and the trace is present and complete enough to decide.
- **FR-013**: Retry-safety MUST be computed on the server from the recorded turn (trace tool calls plus each tool's declared access/reversibility), not from client state. Any tool whose reversibility is undeclared, or any call that cannot be resolved to a registered tool, MUST make the turn not retry-safe.
- **FR-014**: Every write-access tool MUST declare a reversibility class: `reversible` (a domain-owned undo exists) or `irreversible`. A `reversible` declaration MUST also name its compensating tool (`undo_tool`) and a one-line `undo_note` describing what the undo cannot restore, so a later undo-then-regenerate phase can consume it without changing the declaration shape. Read-access tools declare nothing. A tool registered with write access and no declaration MUST fail registration (pre-v1 hard cut, no default).
- **FR-015**: A retry run MUST execute with all write-access tools blocked and memory admission skipped. Retry MUST NOT re-execute any tool call from the original turn, and MUST NOT create a new confirmation request.
- **FR-016**: When Retry is not allowed, the system MUST return a machine-readable reason code and a human-readable explanation naming the action(s) taken. The server MUST refuse an ineligible retry request with the same reason.
- **FR-017**: A completed retry MUST create a new assistant message with its own trace, link it to the message it replaces, and mark the replaced message superseded. The superseded message is retained (with its trace and feedback) and hidden from the default thread view and from the context of later turns.
- **FR-018**: A retry request MUST append a `retry_requested` feedback record on the replaced message, distinguishable from a thumb, even if the retry later fails.
- **FR-019**: A failed or cancelled retry MUST leave the original reply visible and unchanged and tell the person the retry failed.
- **FR-020**: Only one retry or turn may run per thread at a time; a second request is refused with the existing busy behavior (Phase 159 thread identity).
- **FR-021**: No v1 path performs automatic rollback or undo of a past action. A reversible-only turn is not retry-safe in v1 (Clarifications, Deferred).

**Interface**

- **FR-022**: Each assistant reply MUST show thumbs up, thumbs down and Retry on hover and on keyboard focus within the reply, and without hover on touch. Controls MUST have accessible names, pressed state for the current rating, and a disabled-with-reason state for Retry.
- **FR-023**: The reason for an unavailable Retry MUST be exposed as text available to keyboard and screen-reader users, not only as a hover tooltip.
- **FR-024**: Ratings MUST persist across reload and across clients, and MUST update optimistically with revert on failure.
- **FR-025**: The trace panel MUST show, per message, the current rating, the rating history, and retry links in both directions (US5).
- **FR-026**: The server MUST expose: set/clear rating for a message; read feedback and retry eligibility for a batch of message ids (same shape idea as the batch trace endpoint, so the chat list loads in one call); and a live-turn retry request on the WebSocket. Contracts are fixed in `plan.md`; new REST routes follow the OpenAPI rules (`response_model`, `summary`, `description`, explicit `operation_id`), and `@ze/client` types are regenerated.
- **FR-027**: Feedback and message supersession MUST be included in data export and removed by data deletion, like the messages they refer to.

**Boundaries**

- **FR-028**: This phase MUST NOT add a feedback consumer: no calibration run, no threshold change, no routing/admission use, no procedure candidate or promotion, no ranking change, no memory write.
- **FR-029**: Pre-v1 hard cut: no compatibility shim, dual-write, or fallback for messages created before this phase. Older messages show feedback controls; their Retry eligibility follows FR-013 (a missing trace means unavailable).

### Key Entities

- **FeedbackRecord**: immutable evidence of a user reaction to one assistant message. Kind `thumbs_up`, `thumbs_down`, `cleared`, `retry_requested`. Cites the message, thread, trace presence, provenance, confidence. Append-only; current rating is derived from the latest rating-kind record.
- **Current feedback view**: derived per message: current rating (or none), history, retried-by link. Read model, not stored separately.
- **RetryEligibility**: derived per message: `available`, or `unavailable` with a reason code (`not_latest`, `has_write_action`, `has_reversible_action`, `has_irreversible_action`, `confirmed_action`, `workspace_run`, `trace_unavailable`, `unknown_tool`, `turn_pending`, `busy`, `disconnected`) and text naming the actions.
- **Superseded message link**: `replaced_by` / `replaces` relation between assistant messages.
- **Tool reversibility declaration**: per write-access tool, `reversible` or `irreversible`, used by eligibility and by the explanation text.
- **MessageTrace**: unchanged data; now referenced by feedback and must stay readable while feedback exists.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person can rate any delivered assistant reply in one action, and the rating is visible after reload on 100% of tested cases.
- **SC-002**: For 100% of rated replies that have a trace, the routing envelope, every System One judgment row, memory chunks, and tool calls are retrievable from the feedback record's message id with no other key.
- **SC-003**: In the test matrix of actions (reminder, loop, goal, workflow, remembered fact, workspace run, sent email, outreach, calendar create, approved confirmation), Retry starts a run for 0 of them, and shows a correct reason for 100%.
- **SC-004**: In 100% of retry runs, zero write-access tool calls execute and zero `memory_facts` rows are written.
- **SC-005**: For text-only turns, Retry replaces the reply in the thread and the new reply is visible within the same time budget as a normal reply for that turn.
- **SC-006**: Zero `memory_facts`, fact embeddings, or memory-feed items are created by any feedback action.
- **SC-007**: No code path reads feedback during a turn (guarded by a test), so enabling the feature changes no routing, admission or reply behavior.
- **SC-008**: Controls and the unavailable reason are usable by keyboard only and announced by a screen reader in the web accessibility checks.

## Deferred: Undo-then-Regenerate (future phase)

Phase 180 ([Retry Rollback](../180-retry-rollback/spec.md)) delivers this deferred work.

The user wants automatic rollback of a turn's reversible actions followed by regeneration. It is out of scope here and becomes its own phase. This phase only makes the declaration shape ready for it (FR-014). Inventory of WRITE tools as found in code on 2026-10-09 (file:line of the `def`):

Reversible, with a domain undo:
- `set_reminder` → `cancel_reminder`: `plugins/ze-calendar/ze_calendar/agents/reminders/tools.py:31` / `:91`
- `create_goal` → `abandon_goal`: `core/automation/ze-automation/ze_automation/agents/goals/tools.py:144` / `:298` (`pause_goal` `:229` ↔ `resume_goal` `:245` toggle; `resume_goal` may start autonomous work, so irreversible)
- `create_workflow` → `delete_workflow`: `core/automation/ze-automation/ze_automation/agents/workflow/tools.py:139` / `:259`; `enable_workflow` `:232` ↔ `disable_workflow` `:247`; `update_workflow` `:191` and `edit_workflow_steps` `:288` are restorable from the Phase 108 revision log
- `remember_fact` → `forget_fact`: `plugins/ze-personal/ze_personal/agents/companion/tools.py:28` / `:74`
- `reprioritize_item` (override can be cleared): `core/arbitration/ze-priority/ze_priority/tools.py:80`
- `set_contact_channel` `plugins/ze-personal/ze_personal/contacts/tools.py:57` and `confirm_project_membership` `plugins/ze-personal/ze_personal/social/tools.py:108` (restore prior value; needs a stored prior state)
- `create_event` `plugins/ze-calendar/ze_calendar/agents/calendar/tools.py:58`: deletable only when attendee-free; an invite sent to others cannot be recalled

Irreversible:
- `send_email` `plugins/ze-messenger/ze_messenger/agents/messenger/tools.py:113`; `archive_email` `:168` (no Ze unarchive tool); `draft_email` `:88` is harmless but still a write tool
- `delete_event` `.../calendar/tools.py:162` and `update_event` `:108` (prior state is not stored)
- `delete_workflow` `.../workflow/tools.py:259`, `trigger_workflow` `:274`, `cancel_workflow_run` `:336`, `steer_goal` `.../goals/tools.py:24`, `abandon_goal` `:298`, `cancel_reminder` `.../reminders/tools.py:91` (they are the undo of another tool, but themselves lose state or start autonomous work)
- workspace: `workspace_write` `core/ops/ze-workspace/ze_workspace/tools.py:309`, `workspace_delete` `:329`, `workspace_run` `:348`, `workspace_run_skill_script` `:386`, `ingest_workspace_file` `:452`, `workspace_reset` `:481`
- prospecting outreach and ingestion writes

What the future phase must still settle: a per-domain undo executor, ordering of undos, partial-failure handling, whether the regenerated reply may re-offer the undone action, and how an undo is recorded in the action ledger (Phase 135 `supersedes`/`retry_of`).

## Assumptions

- Single user (`single-user-model.md`): feedback has no per-user key; "who rated" is implicit.
- Ratings are two-valued; no stars, no reason chips, no free text in v1 (FR-010). A reason-tag extension is a later phase once the consumer is known.
- The user message that produced a reply is always the message immediately before it in the thread; retry uses that.
- Existing read-access tools have no side effects. Reading can still hit paid external services (cost) — acceptable on retry; cost shows in the normal telemetry.
- Web search (`openrouter:web_search`) is a read tool.
- Implicit negative signal from Retry is recorded as `retry_requested`, never as `thumbs_down`, so consumers can tell them apart.
- Mobile/touch behavior follows the existing chat message action patterns (Phase 117) and the `apple-design` guidance used there.
- The WebSocket remains the transport for turns (`/ws`); feedback uses REST so it works offline-from-socket.
- Owning package for the ledger is `ze-memory` (next `zm` migration, `zm024`), mirroring `action_records` (`zm021`). Retry-safety evaluation lives in `ze-core`; tool reversibility declarations live in `ze-agents` (`@tool`), with each plugin declaring its own. Plugins use only `ze_sdk` surfaces; `ze_core` is not imported by plugins.
- Doctrine functions served: Perception (observes the reaction), Action (retry safety reads what Action did), Governance (consent/reversibility gate on Retry). Memory is custodian only.
- Eval scenarios: `eval/scenarios/` gains a retry-safe and a retry-refused scenario; no calibration run is added.
