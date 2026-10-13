# Feature Specification: Retry Rollback

**Feature Branch**: `180-retry-rollback`

**Created**: 2026-10-13

**Status**: Ready to implement

**Input**: User description: "Automatic rollback for Retry: when the user retries a reply whose turn ran reversible WRITE tools, undo those actions, then regenerate. Today (phase 165) Retry is refused for such turns via retry_eligibility; every WRITE @tool already declares reversibility plus undo_tool/undo_note/effect_phrase, and that declaration was designed for this. Rollback should leave an honest ActionRecord."

**Governed by**: [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md), [`specs/arch/claim-topology.md`](../../arch/claim-topology.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md), [`specs/arch/single-user-model.md`](../../arch/single-user-model.md).

**Depends on**: Phase [165](../165-response-feedback-retry/spec.md) (Retry, eligibility, reversibility declarations, supersession; this phase implements its "Deferred: Undo-then-Regenerate" section), 135 and 136 (action-record ledger and instrumentation), 152 (per-delegate confirmation), 169 (`track_loop` outcomes), 127 (priority overrides), 108 (workflow revisions, not used here; see Deferred).

**Does not start**: a standalone Undo control without regeneration, rollback of any reply other than the latest, redo of undone actions after a failed regeneration, rollback of irreversible actions, new ActionRecord instrumentation for tools that write none today, undo for calendar events, contact channels, project membership, or workflow edits.

---

## Overview

Phase 165 shipped Retry with a hard rule: if the turn wrote anything, Retry is unavailable. That rule is safe but blunt. A person who says "remind me to call mum at 4" and gets a reminder at the wrong time cannot press Retry. They must cancel the reminder by hand and ask again.

Most of what Ze writes inside a conversation can be undone cleanly by Ze itself: a reminder can be cancelled, a goal abandoned, a workflow deleted, a remembered fact forgotten, a tracked loop dropped, a priority override restored. Phase 165 made every WRITE tool declare this (`reversibility`, `undo_tool`, `undo_note`, `effect_phrase`) so this phase could use it.

This phase makes Retry work for those turns. When the latest reply's turn ran only actions Ze can undo cleanly, Retry shows the person what it will undo, asks once, undoes those actions in reverse order through each domain's own undo, and then regenerates the reply. The regenerated turn may take reversible actions again (so the corrected reminder gets set), but it can never start an irreversible one.

Three rules carry over from 165 unchanged: eligibility is decided on the server; unknown never means safe; and nothing irreversible is ever repeated.

### Per-call reversibility

A tool being declared reversible is not enough. Whether one particular call can be undone depends on what it did:

- `track_loop` may create a new loop, or confirm, reinforce or revive one the person already had. Dropping an existing loop would destroy something that predates the turn. Only a call that created the loop is cleanly undoable.
- `enable_workflow` on a workflow that is already enabled changes nothing. Disabling it afterward would change state the turn never touched.
- `forget_fact` works from a free-text query. An undo must target the exact fact the turn wrote, not whatever matches a phrase.

So each reversible call states, at the moment it runs, whether it can be undone and exactly how (an **undo payload**). A call without a payload is not undoable, and a turn that contains one is not rolled back.

## Clarifications

### Session 2026-10-13 (scope pin, before drafting)

The user pinned scope through the Maestro (all recommendations accepted):

- Q: How does rollback know what to undo? → A: Each reversible tool returns an undo payload in its result only when this call can be undone cleanly; the trace stores it per tool call. No payload means not undoable this time. Undo tools gain an id-targeted path where needed (`forget_fact` by fact id).
- Q: What does the regenerated turn run with? → A: Reversible WRITE tools allowed, irreversible WRITE tools blocked. A confirmation gate may pause the retry like a normal turn.
- Q: Consent before undoing? → A: A two-step Retry control in the client that lists what will be undone; the server re-checks eligibility. Text-only replies keep one-press Retry.
- Q: Which tools? → A: `set_reminder`, `create_goal`, `create_workflow`, `enable_workflow`, `disable_workflow`, `remember_fact`, `track_loop` (only when it created the loop), and `reprioritize_item`, newly made reversible with an undo that restores the prior override, or only clears the new one if the prior cannot be restored (then its undo note says so).
- Q: Approved confirmations and mixed turns? → A: A reversible action approved at a confirmation gate can be rolled back (the consent step asks again). Any irreversible action, workspace run, or call without an undo payload still refuses Retry. No partial rollback of a mixed turn.
- Q: Order and partial failure? → A: Undo first, in reverse call order; stop at the first failed undo; no regeneration then, the original reply stays and is marked partly rolled back. If every undo succeeds and regeneration fails, the undo stays (no automatic redo); the original reply shows a notice and Retry stays available as text-only.
- Q: Ledger and trace? → A: Undos run through each domain's own undo tool so the domain's normal ActionRecord is emitted, linked to the original action's record when one exists. The new reply's trace gets a rollback section. No new ActionRecord instrumentation for `remember_fact`, `track_loop`, `enable_workflow`, `disable_workflow`.
- Q: Deferred? → A: Standalone Undo, rollback of older replies, redo after failed regeneration.

### Session 2026-10-13 (/speckit-clarify)

- Q: Does a text-only Retry (empty undo plan) keep the 165 all-writes-blocked policy? → A: No. One retry policy for every Retry: reversible writes allowed under normal gates, irreversible writes blocked. One-press Retry stays when nothing is undone.
- Q: A rollback retry pauses at a confirmation and the person denies it; does the post-denial reply supersede the retried reply? → A: Yes. The undo already happened, so the post-denial reply supersedes the retried reply like any completed retry.
- Q: How does the server guard against undoing a plan the person did not see? → A: The retry request carries the ids of the plan entries the person confirmed; the server recomputes the plan under the thread lock and refuses with `plan_changed`, changing nothing, if they differ.
- Q: Is rollback still offered for `create_goal` / `create_workflow` after autonomous work started (milestone executed, workflow ran)? → A: Yes. The consent step shows the undo note ("does not undo work already started"); the undo stops further work.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retry a reply that set something up (Priority: P1)

A person asks "remind me to call mum at 4". Ze sets the reminder and replies. The person meant 4 tomorrow, not today, and presses Retry. Retry shows "Retry will undo: set a reminder 'call mum'. Does not recall a notification already shown." with Continue and Cancel. The person presses Continue. Ze cancels the reminder, answers the same message again, and the new reply replaces the old one. If the new turn sets a reminder again, it is a fresh reminder that this new reply owns.

**Why this priority**: This is the feature. Without it Retry stays refused for every turn that did anything useful.

**Independent Test**: Send "remind me to stretch in 10 minutes". Press Retry, confirm. Verify the original reminder is cancelled in the reminder store, a new reply replaces the old one, and the new reply's trace shows a rollback section naming the cancelled reminder.

**Acceptance Scenarios**:

1. **Given** the latest reply's turn ran only reversible calls that each carry an undo payload, **When** eligibility is evaluated, **Then** Retry is available and the server returns the undo plan: one entry per call, in the order they will be undone, each with its effect phrase and undo note.
2. **Given** an available Retry with a non-empty undo plan, **When** the person presses Retry, **Then** the control asks for confirmation and lists every planned undo with its note before anything changes; Cancel changes nothing.
3. **Given** the person confirms, **When** the retry runs, **Then** each planned undo runs in reverse call order through the owning domain's undo, then the reply is regenerated for the same user message, and the new reply supersedes the old one exactly as in phase 165.
4. **Given** a retry request for a reply with a non-empty undo plan, **When** the request does not carry the confirmed plan entry ids, or they differ from the plan the server recomputes, **Then** the server refuses it (`plan_changed` on a mismatch) and nothing is undone.
5. **Given** a reply with an empty undo plan (text-only or read-only turn), **When** the person presses Retry, **Then** it is one press with no confirmation step, as in phase 165; the regenerated turn runs under the one retry policy (FR-019).
6. **Given** a completed rollback retry, **When** the new reply's trace is opened, **Then** a Rollback section lists each undone action (what it was, what was undone, outcome) and links to the replaced reply.
7. **Given** a conductor or compound turn with several reversible calls across delegates, **When** it is retried, **Then** every call is in the plan and every one is undone before regeneration.

---

### User Story 2 - Only clean undos are offered (Priority: P1)

A person retries a reply whose turn reinforced a loop they were already tracking, or enabled a workflow that was already on, or mixed a reminder with a sent email. Retry does not offer a rollback that would damage state the turn did not create, and it never undoes part of a mixed turn. It says why.

**Why this priority**: A wrong undo is worse than no Retry. This keeps the 165 safety promise.

**Independent Test**: For each of: `track_loop` reinforcing an existing loop, `enable_workflow` on an already-enabled workflow, a reminder plus a sent email, a workspace run, a call whose undo payload is missing, confirm Retry is unavailable with a reason naming the action, and that a hand-built retry request is refused by the server with the same reason.

**Acceptance Scenarios**:

1. **Given** a reversible call that returned no undo payload (no-op, matched an existing record, or failed), **When** eligibility is evaluated, **Then** Retry is unavailable with a reason saying that action cannot be undone cleanly this time.
2. **Given** any irreversible action, workspace run, or unknown tool in the turn, **When** eligibility is evaluated, **Then** Retry is unavailable with the phase 165 reason, even if other calls are undoable.
3. **Given** a reversible call that ran after the person approved a confirmation gate, **When** it carries an undo payload, **Then** it is undoable like any other, because the consent step asks again.
4. **Given** a write call that failed (`success` false) and carries no undo payload, **When** eligibility is evaluated, **Then** Retry is unavailable (a failed write may have partly run). A failed call that never ran (denied or expired gate) counts as no action, as in phase 165.
5. **Given** any client, **When** it asks the server to retry a reply whose plan it did not see, **Then** the server recomputes the plan from the stored turn and refuses if eligibility says unavailable.

---

### User Story 3 - The regenerated reply can redo, but never escalate (Priority: P1)

After the undo, the person's original message is answered again. If it asked for a reminder, the new turn may set one. It may not send an email, run a workspace command, or take any other irreversible action, even if the model tries. If a reversible action needs the person's confirmation, the retry stops at that confirmation like a normal turn.

**Why this priority**: The point of retrying "remind me at 4" is to get the right reminder. Allowing irreversible actions would let Retry do something the original turn never did.

**Independent Test**: Retry a reminder turn; the new turn sets a new reminder (allowed). In a test, force the regenerated turn to call `send_email`; the call is refused at dispatch and the reply says so in words. Retry a `create_goal` turn under a capability mode that requires confirmation; the retry pauses at the confirmation and completes after approval.

**Acceptance Scenarios**:

1. **Given** a rollback retry run, **When** the model calls a reversible WRITE tool, **Then** it runs under the normal capability and constraint gates.
2. **Given** any retry run (rollback or text-only), **When** the model calls an irreversible WRITE tool, **Then** the call is refused at dispatch, nothing runs, and the reply can say so and offer it as a normal request.
3. **Given** a retry run whose reversible write needs confirmation, **When** the gate fires, **Then** the retry pauses and the person sees the normal confirmation prompt; the original reply stays visible and is marked as rolled back and waiting for confirmation.
4. **Given** that paused retry, **When** the person approves or denies and the turn finishes, **Then** its reply supersedes the original reply exactly as a completed retry would (a denial does not keep the original visible, because its actions are already undone).
5. **Given** a completed rollback retry whose new turn set reversible actions, **When** the new reply is the latest, **Then** it is itself retryable with rollback (the chain continues).
6. **Given** a retry run, **When** it ends, **Then** memory admission is skipped, as in phase 165.

---

### User Story 4 - Failure is honest (Priority: P1)

An undo can fail: the goal was already removed, the database is down. A regeneration can fail after the undo succeeded. In each case the person sees exactly what changed and what did not, and nothing is silently redone.

**Why this priority**: A half-rolled-back turn with a reply that still says "I set it" would be a lie.

**Independent Test**: Make the second of three undos fail. Verify the first undo stayed done, the third was not attempted, no regeneration ran, the original reply stays visible with a notice listing done and not-done undos, and its Retry eligibility now reflects the remaining actions. Separately, make regeneration fail after all undos succeed; verify the undos stay, the original reply shows "Ze undid … but could not write a new reply", and Retry is available as text-only.

**Acceptance Scenarios**:

1. **Given** a rollback, **When** an undo fails, **Then** later undos in the plan are not attempted, no regeneration runs, and the person sees which undos succeeded and which did not.
2. **Given** a partly rolled-back reply, **When** it renders, **Then** it stays visible, shows a "partly rolled back" notice naming what was undone, and its stored record of undone actions survives reload.
3. **Given** a partly rolled-back reply, **When** Retry eligibility is evaluated again, **Then** undone calls are excluded from the plan and the call whose undo failed makes Retry unavailable with a reason naming it.
4. **Given** every undo succeeded, **When** regeneration fails or is cancelled, **Then** the undos stay, nothing is redone, the original reply shows a "rolled back, retry failed" notice, and Retry is available again with an empty undo plan.
5. **Given** an undo returns an error result rather than raising (for example "No reminder found"), **When** the executor reads it, **Then** it counts as a failed undo, never as success.

---

### User Story 5 - Rollback is on the record (Priority: P2)

Later, someone wants to know what happened to that reminder. The reminder's own history shows it was cancelled, and the cancellation is linked to the reply that was retried. The new reply's trace says what it rolled back.

**Why this priority**: Doctrine requires honest evidence for every action. Rollback is an action.

**Independent Test**: Roll back a `set_reminder` turn. Read the action ledger: the cancellation ActionRecord exists, names the retried message in its context, and supersedes the original reminder-create ActionRecord. (Code check 2026-10-13: of the in-scope create and undo tools, only reminders write ActionRecords today; goal and workflow records cover executions, not tool-level create/abandon/delete.) Read the new reply's trace: its rollback section matches.

**Acceptance Scenarios**:

1. **Given** an undo through a tool that writes an ActionRecord today (`cancel_reminder`, the undo of `set_reminder`), **When** it runs, **Then** the domain's normal ActionRecord is written for the undo, carrying the retried message id, and its `supersedes` points to the original create record when that record can be found.
2. **Given** an undo through a tool that writes no ActionRecord today (`abandon_goal`, `delete_workflow`, `enable_workflow`/`disable_workflow`, `forget_fact`, `drop_loop`, the priority restore), **When** it runs, **Then** no new ledger instrumentation is added; the undo is recorded on the retried message and the new reply's trace only.
3. **Given** any rollback, **When** it ends (success, partial, or regeneration failure), **Then** the retried message stores one durable rollback record per planned undo with its outcome, and the phase 165 `retry_requested` feedback record is written as before.

---

### User Story 6 - Reprioritization can be undone (Priority: P2)

A person says "make the tax loop more urgent" and Ze reorders priorities. They retry. Ze restores the priority order that held before the turn.

**Why this priority**: Named in the brief; it is the one tool this phase newly makes reversible.

**Independent Test**: With an existing override on item A, reprioritize A again; retry with rollback; verify the new override is superseded and the earlier override is active again with its original submitted time. With no earlier override, verify the new override is superseded and nothing else changes.

**Acceptance Scenarios**:

1. **Given** `reprioritize_item` wrote a new override that superseded an earlier one, **When** it is undone, **Then** the new override is superseded and the earlier override's effect is restored, keeping its anchor, relation, original submitted time and pin state. (Code check 2026-10-13: `priority_overrides` keeps superseded rows, so a faithful restore needs no migration; the clear-only fallback in FR-008 is not expected to be used.)
2. **Given** `reprioritize_item` wrote a new override with no earlier one, **When** it is undone, **Then** the new override is superseded and the item returns to Ze's own ranking.
3. **Given** `reprioritize_item` returned no-op, clarification or error, **When** eligibility is evaluated, **Then** the call has no undo payload and counts as no action only if it wrote nothing (no-op and clarification write nothing; see FR-008).
4. **Given** the item's override was changed again after the turn (by REST drag reorder), **When** the undo runs, **Then** it fails cleanly instead of overwriting the later change.

---

### Edge Cases

- The reminder fired between the reply and the retry: `cancel_reminder` cannot recall it. The undo note already says so; the undo still marks it cancelled if the store allows, otherwise it fails and the partial-rollback path applies.
- The goal created by the turn has started executing a milestone: rollback is still offered; the consent step shows the undo note that work already started is not undone; abandoning stops further work.
- The workflow created by the turn already ran once: rollback is still offered; deletion does not undo the run and the undo note in the consent step says so.
- A text-only Retry whose regenerated turn sets a reminder the first reply missed: allowed (one retry policy); the new reply is itself rollback-eligible.
- The person edited or deleted the created record by hand before retrying (deleted the reminder in the UI): the undo returns "not found" and fails; the partial-rollback path applies and the notice says the item was already gone.
- Two reversible calls touch the same record (create then enable a workflow): reverse order undoes enable, then deletes; both are in the plan.
- A thread receives a new user message after the reply: the reply is no longer the latest; Retry is unavailable (`not_latest`), as in 165.
- The socket drops mid-rollback: the run continues server-side under the thread lock; on reconnect the client sees the final state (superseded, partly rolled back, or rolled back with failed retry) from the stored message.
- Two retry presses: the second is refused with `busy` (phase 165 / 159).
- Rollback plan computed for an old trace without undo payloads (written before this phase): no payload, so Retry stays unavailable. No backfill (pre-v1 hard cut).
- A delegate call (`delegate_to_agent`) itself is not a write; its nested calls are flattened and each judged, as today.

## Requirements *(mandatory)*

### Functional Requirements

**Per-call undo payload**

- **FR-001**: Every REVERSIBLE WRITE tool MUST, on a call that can be undone cleanly, return an undo payload naming the exact arguments its declared undo needs to reverse that call and nothing else. On any other outcome (no-op, matched or changed a record that existed before the turn, error, partial) it MUST return no payload.
- **FR-002**: The turn's recorded trace MUST store, per tool call, the undo payload (when present), the agent that ran the call, and enough identity to order calls. Stored payloads MUST contain identifiers only, never message content.
- **FR-003**: A REVERSIBLE declaration MUST remain the static contract; the payload is the per-call fact. A reversible call with no payload MUST be treated as not undoable.
- **FR-004**: The undo for `remember_fact` MUST retract exactly the fact the call wrote, by id, and MUST restore the facts that write marked contradicted (same predicate and subject, or semantic contradiction), so memory reads as it did before the turn. `forget_fact` (or an id-targeted path in the same domain) MUST support this without a free-text match. The undo MUST fail rather than restore a displaced fact that was changed or retracted again after the call.
- **FR-005**: `track_loop` MUST return a payload only when its outcome was `created`.
- **FR-006**: `enable_workflow` and `disable_workflow` MUST return a payload only when they changed the workflow's state.
- **FR-007**: `set_reminder`, `create_goal`, `create_workflow` MUST return a payload naming the created record on success.
- **FR-008**: `reprioritize_item` MUST be declared REVERSIBLE with a new undo that restores the override state that held before the call: supersede the new override and reinstate the earlier active override for the same item, if any, with its original submitted time and pin. If the store cannot reinstate it faithfully, the undo MUST only clear the new override and its undo note MUST say the earlier override is not restored. The undo MUST fail rather than overwrite an override written after the call. Calls that wrote nothing (no-op, clarification, error) return no payload and are not actions.

**Eligibility and plan**

- **FR-009**: Retry eligibility MUST remain computed on the server from the stored turn. A reply is rollback-eligible when it is the latest reply and every write call that ran (after excluding denied/expired gates and calls already undone) is REVERSIBLE and carries an undo payload, and no workspace run started.
- **FR-010**: Any irreversible write, workspace run, unknown tool, missing trace, or reversible call without a payload MUST make Retry unavailable, with a reason code and text naming the action(s). New reason codes cover "cannot be undone cleanly this time" and "an earlier undo failed".
- **FR-011**: An approved confirmation MUST NOT by itself make a reversible call ineligible (supersedes the 165 `confirmed_action` rule for reversible calls with a payload). It still blocks when the approved call is irreversible.
- **FR-012**: An eligible reply MUST expose its undo plan: ordered entries (reverse call order), each with the effect phrase, the undo note, and an opaque entry id. The plan MUST be available in the batch feedback read, and a `plan_changed` refusal MUST carry the recomputed plan.
- **FR-013**: A retry request for a reply with a non-empty plan MUST carry the ids of the plan entries the person confirmed. The server MUST recompute the plan under the thread lock and refuse with `plan_changed`, changing nothing, when the confirmed ids are missing or differ from the recomputed plan. A request for a reply with an empty plan carries no ids.
- **FR-013a**: Rollback MUST still be offered for `create_goal` and `create_workflow` after autonomous work started; the plan entry's undo note states that work already started is not undone.

**Rollback execution**

- **FR-014**: A confirmed rollback retry MUST, while holding the thread's turn lock, recompute eligibility and the plan from the stored turn, then run each undo in plan order through the owning agent's declared undo tool with the stored payload, with that agent's normal dependencies, before any regeneration.
- **FR-015**: An undo MUST count as succeeded only when the undo tool returned success. An error result, an exception, or a missing owning agent or undo tool MUST count as failed.
- **FR-016**: On the first failed undo the executor MUST stop, MUST NOT run later undos, MUST NOT regenerate, and MUST persist the outcome of every attempted undo on the retried message.
- **FR-017**: After every undo succeeds, the executor MUST regenerate as in phase 165 (rewind past the original exchange, same user message). If regeneration fails or is cancelled, the undos MUST stay, nothing is redone, and the retried message MUST record that it was rolled back with a failed retry.
- **FR-018**: The retried message's durable rollback record MUST hold, per planned entry: tool, undo tool, outcome (`undone`, `failed`, `not_attempted`), time, and failure reason when failed. Eligibility MUST read it (undone calls drop out; a failed undo blocks).

**Regenerated turn**

- **FR-019**: There is one retry policy. Every retry run, whether its plan was empty or not, MUST block IRREVERSIBLE WRITE tools at dispatch with the phase 165 refusal, and MUST allow REVERSIBLE WRITE tools under the normal capability, constraint and confirmation gates. Memory admission stays skipped. This replaces the 165 rule that a retry blocks every write.
- **FR-020**: A retry run that reaches a confirmation gate MUST pause like a normal turn. The pending turn MUST remember which message it replaces and that it is a retry run, so the reply produced after resume, whether the person approved or denied, supersedes the retried message and the resumed run keeps the retry policy. If the resolution produces no reply (a denial that discards the pending turn, or a timeout), the retried message MUST move to "rolled back, retry did not finish" and Retry is available again with an empty plan. While paused, the retried message shows it was rolled back and is waiting for confirmation.
- **FR-021**: Reversible calls made by a retry run MUST carry undo payloads like any other call, so the new reply is itself rollback-eligible.

**Record and trace**

- **FR-022**: Every ActionRecord written while an undo runs MUST carry the retried message id in its context and `supersedes` set to the latest succeeded record for the same authoritative record that a different action kind wrote (the create), when one exists. Today this applies to `cancel_reminder`. Missing original records MUST NOT block the undo.
- **FR-023**: This phase MUST NOT add ActionRecord instrumentation to any tool that lacks it today (`remember_fact`, `forget_fact`, `track_loop`, `drop_loop`, `create_goal`, `abandon_goal`, `create_workflow`, `delete_workflow`, `enable_workflow`, `disable_workflow`, `reprioritize_item`, the priority restore). Their undos are recorded on the retried message and the new reply's trace.
- **FR-024**: The new reply's trace MUST include a Rollback section: retried message id and each entry's effect phrase, undo tool, outcome. The trace panel MUST show it, and the retried message's trace view MUST show its rollback record and notice.
- **FR-025**: The phase 165 `retry_requested` feedback record MUST still be written on every retry request, rollback or not.

**Interface**

- **FR-026**: The web Retry control MUST be one press for an empty plan, and two-step for a non-empty plan: the second step lists every planned undo with its effect phrase and undo note, readable by keyboard and screen reader, with Continue and Cancel.
- **FR-027**: The web client MUST render the three end states on the retried reply: superseded (as 165), partly rolled back (notice naming undone and not-undone actions), and rolled back with failed retry; and the paused state (rolled back, waiting for confirmation). These MUST survive reload.
- **FR-028**: REST and WS contracts MUST follow the OpenAPI rules (response_model, summary, description, operation_id) and the generated client types MUST be regenerated.

**Boundaries**

- **FR-029**: No standalone Undo, no rollback of a non-latest reply, no automatic redo, no rollback of irreversible actions, no backfill of payloads for turns recorded before this phase (pre-v1 hard cut).
- **FR-030**: Plugins MUST return undo payloads using `ze_sdk` surfaces only; `ze_core` is not imported by plugins.

### Key Entities

- **Undo payload**: per tool call; the exact arguments for the declared undo tool that reverse that call only. Absent means not undoable.
- **Undo plan**: derived per reply; ordered entries (reverse call order) with effect phrase, undo note, entry id. Read model, not stored. Entry ids are deterministic from the stored turn so the client's confirmed ids can be compared with the server's recomputed plan.
- **Rollback record**: stored on the retried message; one entry per planned undo with outcome and time; plus the overall state (`rolled_back_awaiting_confirmation`, `partial`, `rolled_back_retry_failed`, `superseded`). "Retry did not finish" after a confirmation without a reply uses `rolled_back_retry_failed`.
- **Rollback trace section**: on the new reply's trace; mirrors the rollback record and links back.
- **Retry eligibility** (extended from 165): adds the plan and new reason codes.
- **ActionRecord** (unchanged shape): undo actions use existing producers, with `supersedes` and message context.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For each of the eight in-scope tools, a turn that ran only that tool (in its clean-undo outcome) can be retried with rollback, and after rollback the domain state matches the state before the turn in 100% of tested cases (apart from what the tool's undo note names).
- **SC-002**: In the refusal matrix (reinforced loop, no-op enable, reminder + email, workspace run, missing payload, unknown tool, failed earlier undo), Retry starts no undo and no run in 100% of cases, through the UI and through a hand-built request.
- **SC-003**: In 100% of retry runs (rollback and text-only), zero irreversible write calls execute.
- **SC-003a**: In 100% of tests where the confirmed plan ids differ from the recomputed plan, zero undos run and the server returns `plan_changed`.
- **SC-004**: In a forced mid-plan undo failure, 0 later undos run, 0 regenerations start, and the stored rollback record matches the real outcome of every entry.
- **SC-005**: Every rollback undo through a tool that writes ActionRecords today (`cancel_reminder`) has a matching ActionRecord naming the retried message and superseding the create record; 100% of rollbacks have a matching Rollback trace section and stored rollback record.
- **SC-006**: A person can read what Retry will undo and confirm or cancel using only the keyboard, and a screen reader announces the list.
- **SC-007**: A rollback retry of a single-action turn completes within the normal reply time for that turn plus no more than 2 seconds.

## Assumptions

- Single user; consent is the person's own confirmation, no roles.
- Undo tools keep their LLM-facing descriptions; the rollback executor calls them directly with stored payloads, outside the model's tool loop but through the agent's normal dispatch (hooks, logging).
- The original action ActionRecord can be located by its authoritative record id (reminder id, goal id, workflow id) for `supersedes`; when it cannot, the link is omitted.
- The durable rollback record lives on the retried message (ze-core `messages`, next `zc` migration); no new table.
- Turns recorded before this phase have no payloads and stay non-retryable when they wrote anything.
- Eval: `eval/scenarios/` gains rollback-retry and rollback-refused scenarios; no calibration run.
- Doctrine functions served: Action (undo is an action, recorded), Governance (consent step, unknown never safe, no escalation in the regenerated turn), Perception (the 165 retry signal, unchanged). Memory is custodian of the ledger and facts only.
- Owning packages: rollback executor and eligibility in `ze-core` (`ze_core/conversation/`); undo payload contract in `ze-agents` (exported via `ze-sdk`); per-tool payloads in `ze-calendar`, `ze-personal`, `ze-automation`, `ze-worldstate`, `ze-priority`, and `ze-memory` (id-targeted retraction); WS/REST and supersession in `ze-api`; UI in `ze-web` and `@myguyze/ze-client`.

## Deferred

- Standalone Undo for a reply without regeneration.
- Rollback of replies other than the latest.
- Redo of undone actions after a failed regeneration.
- Undo for `create_event` (attendee-free), `set_contact_channel`, `confirm_project_membership`, `update_workflow` / `edit_workflow_steps` (restorable from the phase 108 revision log).
- ActionRecord instrumentation for `remember_fact`, `track_loop`, `enable_workflow`, `disable_workflow`, `reprioritize_item`.
