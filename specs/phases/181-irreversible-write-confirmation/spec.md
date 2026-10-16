# Feature Specification: Irreversible Write Confirmation

**Feature Branch**: `181-irreversible-write-confirmation`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User description: "One rule, enforced in code wherever a tool runs (agentic loop, delegate/conductor fan-out, workflow and goal executors): every WRITE tool declared IRREVERSIBLE asks the user before it acts, regardless of agent, intent or route. Use the 165 reversibility declaration. Decide reversible writes, unattended runs, composition with the capability gate, budget gate and constraint veto, the fate of `Intent.mode` and `_primary_intent`, the confirmation UX and Retry interplay. Confirm only at a point where the graph can checkpoint, never inside a concurrent child task."

**Governed by**: [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md) (action and governance functions; user agency), [`specs/arch/companion-conductor-roadmap.md`](../../arch/companion-conductor-roadmap.md) (151–161), [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md), [`specs/arch/langgraph-orchestration.md`](../../arch/langgraph-orchestration.md). Phases [113](../113-hardening-sweep/spec.md) (request_id-keyed confirmations, spend budget), [144](../144-constraint-veto-mail-calendar/spec.md) (constraint veto), [151](../151-fat-delegate-aci/spec.md)–[158](../158-parallel-subtask-gates/spec.md) (conductor, per-delegate and per-subtask gates), [161](../161-workspace-chat-first/spec.md) (workspace chat-first), [165](../165-response-feedback-retry/spec.md) (reversibility declaration, retry_mode), 177 (interruption governor), 180 (retry rollback).

**Depends on**: 165 and 180 on `main` (they are). The 171 Follow-ups floor's goal-local fix (goals declare read first; goal write tools confirm at tool level) lands before or with this phase; this phase replaces that local confirmation.

**Does not change**: the 165 reversibility vocabulary itself (`REVERSIBLE` / `IRREVERSIBLE`, `undo_tool`, `undo_note`, `effect_phrase`), Retry (a retry still never asks and never writes), 180 rollback, the routing decision (which agent answers), the 144 constraint matching rules, the 113 budget arithmetic, the 177 governor's classes and budget.

---

## Overview

Today Ze decides whether to ask before acting by agent and intent. The router picks the routed agent's **first declared intent** (`_primary_intent`), and the gate mode follows that intent. Calendar, messenger and workflow declare `read` first. So "delete my 3pm" runs as a read, with no question: `delete_event` is irreversible and constraint-gated, and nothing asks. Messenger's `create` intent is `DRAFT_ONLY`, but it is never chosen, so `send_email` runs without asking. Choosing the intent by embedding was measured on the 171 Follow-ups floor and fails (E5 cannot separate create/read/update/delete; margins about 0.01).

The confirmation that does exist has two more defects:

1. **What the user approves is not what runs.** A `CONFIRM` intent runs the agent once in draft mode, pauses, and on approval runs the agent **again** for real. The model decides again on the second run.
2. **Pauses happen inside running code.** Workspace confirmations, the 144 constraint veto and the 152 delegate gate pause from inside the agent's tool loop. On resume the graph re-runs the whole step, so writes made earlier in the same loop can run twice. Inside the parallel fan-out (decompose/compound) it is worse: the step never returns, finished subtasks are not saved, and sibling writes can run twice (an email sent twice). Vigil found this on the 171 Follow-ups floor.

This phase replaces all of it with one rule on the tool, not the agent:

> **A WRITE tool that asks first never runs until the user approves that exact call.** Every IRREVERSIBLE tool asks first unless it opts out with a written reason. REVERSIBLE tools run without asking.

The mechanism is **park and resume**:

- When an agent's loop calls a tool that asks first, the call does not run. Ze records it (tool, exact arguments, effect phrase) as a **parked write**, and the agent's loop stops at that point. Its transcript is saved in the conversation state.
- Other work in the turn finishes normally: parallel subtasks complete, reads run, reversible writes run.
- When all running work has finished or parked, the turn pauses **once**, at a graph step that is saved to the checkpoint. The user sees one confirmation listing every parked write.
- On approval, Ze runs exactly the approved calls with exactly the approved arguments (or the user's edit, where the tool allows edits). Each parked loop then **resumes from its saved transcript with the real results**, so later steps can use what the write returned (for example a new event's id), and the model writes the reply.
- A resumed loop may call another asks-first tool. It parks again, and the user gets a new confirmation.
- On deny, or when the confirmation times out, nothing runs, and Ze says so.

Intent-based gating is deleted (pre-v1 hard cut): `Intent`, `Mode`, the `intents` attribute, `default_mode`, `_primary_intent`, `CapabilityGate`, the `capability_overrides` table and its REST surface, session overrides, the draft-and-re-run confirmation path, the 152 per-delegate gate and the 158 per-subtask gates. The agent-level `enabled` flag stays.

Unattended runs (workflow steps, the goal executor, scheduled jobs) follow the same rule. A workflow or goal plan names the asks-first tools its steps use, and the user approves them when they approve the plan. A call that was not pre-approved holds the run and reaches the user as a push.

Doctrine fit: this is the **action** function under **governance**. Ze may decide and prepare, but an action that cannot be taken back is the user's to approve, and the approval binds Ze to exactly that action. This is user agency made enforceable in code, not left to prompts.

## Clarifications

### Session 2026-10-15 (scope)

Answers marked **(user, Qn)** were given by the user through the Maestro (questions Q1–Q10 in the "181 Irreversible Write Confirmation Handoffs" note). The rest are Spec Architect decisions with the reason; the user may overturn them.

- Q: Which writes ask first? → A: **(user, Q1)** Every IRREVERSIBLE tool asks first by default. A tool opts out only by declaring `asks_first=False` with a required, non-empty `no_ask_reason`; registration fails otherwise, as with the 165 declarations. The phase audits all 35 IRREVERSIBLE tools (table below) and turns true undo pairs into REVERSIBLE tools.
- Q: Do REVERSIBLE writes ask? → A: **(user, Q2)** No. They run; 180 rollback and their `undo_tool` can reverse them. A REVERSIBLE tool cannot declare `asks_first`.
- Q: How does the confirmation suspend and resume? → A: **(user, Q3)** Park and resume. Asks-first calls are parked with their exact arguments; the run suspends only at a checkpoint-safe graph step, never inside a parallel fan-out; after approval each parked loop resumes from its saved transcript with the real tool results; nested conductor → specialist transcripts are saved; a resumed loop may park again; the approved calls run unchanged.
- Q: What does the user see? → A: **(user, Q4)** One confirmation per pause, listing every parked write (its effect phrase and a short summary of its arguments), with **Approve all** and **Deny all**, and **Edit** on items whose tool allows editing (for example an email body). The existing confirmation frame gains an `items` list. It reuses `pending_confirmations`, keyed by `request_id` (113).
- Q: What happens to intents and the capability gate? → A: **(user, Q5)** Deleted, as listed in the Overview. The agent `enabled` flag stays. ze-web's use of the capabilities REST surface is removed with it.
- Q: What happens to the 113 spend budget gate? → A: **(user, Q6)** It becomes its own pause before the turn runs ("this turn may push today's spend over $X — continue?"), independent of writes.
- Q: What happens to the 144 constraint veto? → A: **(user, Q7)** It is checked when a call parks (or would run). A conflict that needs the user's OK is shown on that item in the same confirmation; a hard veto refuses the call outright and nothing is parked. There is no separate pause.
- Q: Unattended runs? → A: **(user, Q8)** Pre-approval at plan time: approving a workflow or goal plan (and each workflow revision, 108) approves the asks-first tools it names for its steps. A call that was not pre-approved holds the run and is pushed through the 177 governor; the user approves or denies from the notification or chat, and the run continues. Unattended is a P2 story inside this phase.
- Q: Workspace? → A: **(user, Q9)** The WorkspaceGate decision (action × origin) becomes a declared pre-call check that feeds the same park mechanism. Workspace tools opt out of the default with that check as their reason; the check parks the call when the gate says to ask. The in-tool `ToolConfirmationRequired` path is deleted.
- Q: Deny and timeout? → A: **(user, Q10)** Nothing runs. Ze replies "Okay, I didn't <effect>" for each denied item. A timeout (`CONFIRM_TIMEOUT_SECONDS`) counts as a deny. Both are recorded on the message trace.
- Q: Retry? → A: **(user, statement)** Unchanged. A retry turn never parks and never opens a confirmation; every WRITE tool stays refused (165). 180's rule that a reply with an irreversible action cannot be retried keeps working.
- Q: Cobble's goal-local confirmation (171 Follow-ups)? → A: **(user, statement)** Replaced by this mechanism; the local confirmation code is deleted.
- Q: What does a deny do to the parked loop? → A: **(user, C2)** The denied calls do not run. Each parked loop resumes with a "the user declined; nothing was done" result for each denied call, so the rest of the turn (other subtasks, reads already done) can still be reported. Code then makes sure the reply contains the "Okay, I didn't <effect>" line for each denied item, so a model that ignores the denial cannot claim the write happened. Reason: with park and resume, a fixed one-line reply would drop the answers of sibling subtasks that finished.
- Q: How many times can one turn pause? → A: **(user, C3)** At most 3 confirmations per user turn. A fourth asks-first call in the same turn is not parked; the loop gets a refusal ("ask the user in your reply instead") and the call does not run. Reason: bounds a model that keeps proposing writes.
- Q: What if the user sends a new message while a confirmation is open? → A: Spec Architect decision, same as today: a new turn that completes on the thread supersedes the open confirmation. Nothing parked runs, the parked loops are discarded, and the trace records "superseded".
- Q: What if a parked call is approved but then fails? → A: The failure is the real tool result. The loop resumes with it and the model reports it; code adds nothing. No automatic retry of the write.

### Session 2026-10-15 (clarify)

Questions C1–C5 in the Handoffs note; the user accepted every recommendation.

- Q: Is the 35-tool audit right? → A: **(user, C1)** Accepted as written (table below).
- Q: What happens after a deny or timeout? → A: **(user, C2)** Each parked loop resumes with "the user declined; nothing was done" for each denied call; code guarantees an "Okay, I didn't <effect>" line per denied item.
- Q: How many confirmations can one user turn open? → A: **(user, C3)** At most 3; a 4th asks-first call is refused (not run) and the model is told to ask in its reply.
- Q: How long does an unattended hold wait? → A: **(user, C4)** 24 hours, then it counts as a deny. Interactive confirmations keep `CONFIRM_TIMEOUT_SECONDS`.
- Q: How precise is plan-time pre-approval? → A: **(user, C5)** Per step (or goal milestone): approving the plan approves the asks-first tools that step names, with any arguments. Editing a step clears that step's pre-approval.

### Irreversible tool audit (accepted as written, user C1)

All 35 WRITE tools declared IRREVERSIBLE on `main` @489f348e. "Ask" keeps the default. "Opt out" declares `asks_first=False` with the reason shown. "→ REVERSIBLE" reclassifies the tool with the named undo tool. "Workspace check" means the WorkspaceGate pre-call check decides (Q9). The constraint-gated tools (marked CG) are still checked by the 144 veto even when they opt out.

| # | Tool | Package | CG | Decision | Reason / undo |
|---|---|---|---|---|---|
| 1 | `send_email` | ze-messenger | CG | **Ask** | Leaves Ze; cannot be unsent. |
| 2 | `archive_email` | ze-messenger | | **Ask** | Changes the user's mailbox; no undo tool. |
| 3 | `draft_email` | ze-messenger | CG | Opt out | "Creates a draft in the user's mailbox; nothing is sent." |
| 4 | `create_event` | ze-calendar | CG | **Ask** | Can send invitations to attendees. |
| 5 | `update_event` | ze-calendar | CG | **Ask** | Can notify attendees; prior values are not kept. |
| 6 | `delete_event` | ze-calendar | CG | **Ask** | Destroys the event; the motivating bug. |
| 7 | `cancel_reminder` | ze-calendar | CG | **Ask** | Destroys a user reminder. |
| 8 | `forget_fact` | ze-personal | | **Ask** | Deletes a memory; cannot be restored. |
| 9 | `set_contact_channel` | ze-personal | | **Ask** | Changes where Ze sends messages for a person. |
| 10 | `confirm_project_membership` | ze-personal | | Opt out | "Records the user's own confirmation of an inferred claim; a later statement corrects it." |
| 11 | `abandon_goal` | ze-automation | | **Ask** | Ends a multi-week goal. |
| 12 | `steer_goal` | ze-automation | | Opt out | "Queues the user's own instruction for the goal; the next milestone reads it." |
| 13 | `pause_goal` | ze-automation | | → REVERSIBLE | undo `resume_goal`. |
| 14 | `resume_goal` | ze-automation | | → REVERSIBLE | undo `pause_goal`. |
| 15 | `update_workflow` | ze-automation | | **Ask** | Changes when an unattended workflow runs. |
| 16 | `edit_workflow_steps` | ze-automation | | **Ask** | Changes what an unattended workflow does; resets its pre-approvals (US5). |
| 17 | `delete_workflow` | ze-automation | | **Ask** | Destroys the workflow. |
| 18 | `trigger_workflow` | ze-automation | | Opt out | "Starts a run now; the run's own asks-first steps are gated by plan pre-approval." |
| 19 | `cancel_workflow_run` | ze-automation | | Opt out | "Stops a run the user asked to stop; the workflow itself is kept." |
| 20 | `close_loop` | ze-worldstate | | Opt out | "Bookkeeping the user asked for; `track_loop` re-opens the concern." |
| 21 | `drop_loop` | ze-worldstate | | Opt out | "Bookkeeping the user asked for; `track_loop` re-opens the concern." |
| 22 | `reprioritize_item` | ze-priority | | Opt out | "A decaying override; the user can reorder again." |
| 23 | `confirm_recurring` | ze-finance | | Opt out | "The user's own classification of an expense." |
| 24 | `dismiss_recurring` | ze-finance | | Opt out | "The user's own classification of an expense." |
| 25 | `ingest_url` | ze-ingestion | | Opt out | "Saves content the user asked to save; nothing leaves Ze." |
| 26 | `ingest_text` | ze-ingestion | | Opt out | "Saves content the user asked to save; nothing leaves Ze." |
| 27 | `add_prospect` | ze-prospecting | | Opt out | "An internal campaign record." |
| 28 | `draft_outreach` | ze-prospecting | | Opt out | "A draft; nothing is sent." |
| 29 | `log_outreach_event` | ze-prospecting | | Opt out | "An internal campaign record." |
| 30 | `workspace_write` | ze-workspace | | Workspace check | WorkspaceGate decides (in-turn writes run). |
| 31 | `workspace_delete` | ze-workspace | | Workspace check | WorkspaceGate decides. |
| 32 | `workspace_run` | ze-workspace | | Workspace check | WorkspaceGate decides. |
| 33 | `workspace_run_skill_script` | ze-workspace | | Workspace check | WorkspaceGate decides (executable approval, `zsk002`, still applies). |
| 34 | `ingest_workspace_file` | ze-workspace | | Opt out | "Saves a workspace file the user asked to save; nothing leaves Ze." |
| 35 | `workspace_reset` | ze-workspace | | Workspace check | WorkspaceGate decides. |

Result: 12 tools ask, 2 become REVERSIBLE, 16 opt out with a reason, 5 follow the workspace check. Tools added after this phase follow the default.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ze asks before it deletes, sends or changes something that cannot be undone (Priority: P1)

The user says "delete my 3pm". Ze finds the event, then shows one confirmation: "Delete a calendar event — Dentist, today 15:00". Nothing is deleted until the user approves. On approval, the event is deleted and Ze replies that it is done. The same happens for "send Ana the notes", whichever agent handles it and however the request was routed (direct routing, the companion delegating, or a compound request).

**Why this priority**: This is the bug. Today these writes run without asking.

**Independent Test**: Send "delete my 3pm" with a mocked calendar. Assert that a confirmation with one item (`delete_event`, exact event id) opens, that the calendar delete was not called before approval, and that it was called exactly once, with the same arguments, after approval.

**Acceptance Scenarios**:

1. **Given** an event at 15:00, **When** the user says "delete my 3pm", **Then** Ze lists the event (read, no question), parks `delete_event` with that event's id, and pauses with one confirmation item.
2. **Given** that confirmation, **When** the user approves, **Then** `delete_event` runs once with the parked arguments, the calendar agent's loop resumes with the real result, and the reply confirms the deletion.
3. **Given** the companion delegates "email Ana the notes" to messenger, **When** messenger calls `send_email`, **Then** the call parks inside the specialist, the companion's loop parks behind its delegate call, and the user sees one confirmation with the email.
4. **Given** a routed agent whose old first intent was `read` (calendar, messenger, workflow), **When** it calls an asks-first tool, **Then** it still parks; routing and intent no longer affect the decision.
5. **Given** a tool that opted out (for example `ingest_text`), **When** the user says "save this", **Then** it runs without a confirmation.
6. **Given** a REVERSIBLE write, **When** an agent calls it, **Then** it runs without a confirmation.

---

### User Story 2 - What I approve is exactly what runs, and the reply uses the real result (Priority: P1)

The user approves "Create a calendar event — Lunch with Ana, Friday 13:00". The event created is that one, with those values. If the agent's plan continues ("then email Ana the invite link"), the resumed loop sees the real new event and its link, and the email it proposes (which parks again, because `send_email` asks) contains that link.

**Why this priority**: Without it, a confirmation is a promise Ze can break: today's draft-then-re-run lets the model choose differently after approval.

**Independent Test**: Park a `create_event` call; after approval, assert the tool ran with byte-identical arguments, the model was not called before the tool ran, and the resumed transcript contains the real tool result as the answer to the original tool call.

**Acceptance Scenarios**:

1. **Given** a parked call, **When** the user approves without editing, **Then** the tool runs with the exact parked arguments, before any further model call.
2. **Given** an editable item (`send_email` body), **When** the user edits and approves, **Then** the tool runs with the parked arguments plus only the edited field changed, and the trace records the edit.
3. **Given** an approved call that returns data, **When** the loop resumes, **Then** the transcript has the real result as the response to the original tool call id, and the model continues from there.
4. **Given** the resumed loop proposes another asks-first call, **When** it calls it, **Then** it parks and a new confirmation opens (a new `request_id`).
5. **Given** a turn has already paused 3 times, **When** the loop proposes a fourth asks-first call, **Then** the call does not run or park; the loop is told to ask the user in its reply.
6. **Given** a server restart while a confirmation is open, **When** the user approves after restart, **Then** the turn resumes from the saved transcript and the approved call runs once.

---

### User Story 3 - A compound request never runs a write twice (Priority: P1)

The user says "what's on my calendar tomorrow, and send Ana the agenda". The read subtask and the messenger subtask run in parallel. The read finishes; `send_email` parks. The turn pauses once, after both subtasks have finished or parked. On approval the email is sent once, the messenger loop resumes, and the reply combines both parts. The read is not run again.

**Why this priority**: This is Vigil's finding: today a pause inside the parallel fan-out can repeat sibling writes.

**Independent Test**: A compound turn with a read subtask and a subtask that calls `send_email`. Assert: one pause; the read subtask's tool ran once in total; `send_email` ran once after approval; the completed subtask's result is in the saved state before the pause.

**Acceptance Scenarios**:

1. **Given** two parallel subtasks where one parks, **When** the other finishes, **Then** its result is saved, and the pause happens only after both have finished or parked.
2. **Given** two subtasks that both park, **When** the turn pauses, **Then** one confirmation lists both items.
3. **Given** approval, **When** the turn resumes, **Then** only the parked subtasks resume; finished subtasks are not run again; each approved call runs exactly once.
4. **Given** a reversible write that ran in a sibling before the pause, **When** the turn resumes, **Then** it does not run again.
5. **Given** "deny all", **When** the turn resumes, **Then** the finished subtask's answer is still in the reply, and the reply says "Okay, I didn't send an email".

---

### User Story 4 - Saying no, or not answering, means nothing happens (Priority: P1)

The user denies the confirmation, or does not answer within the timeout. Nothing parked runs. Ze replies "Okay, I didn't delete a calendar event" (one line per denied item), plus anything else the turn produced. The message trace shows each item as denied or timed out.

**Why this priority**: A confirmation that can be bypassed by silence is not a confirmation.

**Independent Test**: Park `delete_event`, deny; assert the tool never ran, the reply contains the "didn't" line, and the trace marks the item denied. Repeat with the timeout elapsed.

**Acceptance Scenarios**:

1. **Given** an open confirmation, **When** the user denies, **Then** no parked call runs and each parked loop resumes with a "declined" result.
2. **Given** the model's reply after a deny does not mention the denied item, **When** the reply is finalized, **Then** code adds "Okay, I didn't <effect phrase>".
3. **Given** the timeout passes, **When** the confirmation expires, **Then** it is treated as a deny and the user is told (in chat when connected, by push when not, as today).
4. **Given** an open confirmation, **When** the user sends a new message that completes, **Then** the open confirmation is superseded, nothing parked runs, and the trace records "superseded".

---

### User Story 5 - Unattended runs ask once, at plan time (Priority: P2)

The user creates a workflow "every Monday, email me a summary of my week". When they approve the plan, the approval lists "Sends an email" for the step that does it. Every Monday that step runs without asking. If a step calls an asks-first tool the plan did not name (for example it decides to delete an event), that call holds the run, and Ze pushes "Your workflow 'Weekly summary' wants to delete a calendar event — approve?". The user approves or denies from the notification or in chat; the run continues or skips that call.

**Why this priority**: The rule must hold where no one is watching, but interactive turns are where the bug bites today.

**Independent Test**: A workflow whose plan pre-approves `send_email` for step 2. Run it: `send_email` runs unasked. A second workflow step calls `delete_event` (not pre-approved): the run holds, one push goes out, the tool has not run; approving resumes and runs it once.

**Acceptance Scenarios**:

1. **Given** a workflow plan, **When** the user is asked to approve it, **Then** the approval lists, per step, the asks-first tools the step may call, in plain words (effect phrases).
2. **Given** an approved plan, **When** a step calls a pre-approved tool, **Then** it runs without a confirmation, and the trace records that it ran under pre-approval.
3. **Given** a step calls an asks-first tool the plan did not name, **When** it calls it, **Then** the step holds, the governor sends one push (the user asked for this kind of push, so it does not use the discretionary budget), and nothing runs until the user answers.
4. **Given** a held run, **When** the user denies, **Then** the call does not run and the step continues with a "declined" result (the step's `on_failure` policy, 107, applies if the step then fails).
5. **Given** the user edits a workflow's steps, **When** the revision is saved, **Then** the pre-approvals of changed steps are cleared and the next approval lists them again.
6. **Given** a goal plan, **When** the user approves it, **Then** the same pre-approval applies to its milestones, and the goal executor holds and pushes for anything not named.
7. **Given** a scheduled job that calls an asks-first tool, **When** it runs, **Then** it holds and pushes like a workflow step (no scheduled job is exempt).

---

### User Story 6 - Constraint conflicts, budget and workspace use the same confirmation (Priority: P2)

The user has a reviewed constraint "no meetings before 10". They ask "book a call with Rui at 9". The `create_event` confirmation shows the conflict on that item: "This breaks your rule: no meetings before 10". One confirmation, not two. A hard veto refuses the call before it parks. When a turn would push today's spend past the configured budget, Ze asks once before the turn runs. Workspace runs in chat follow the WorkspaceGate's decision through the same park.

**Why this priority**: These are the three other places that pause today; each pauses from inside running code.

**Independent Test**: A reviewed constraint conflicting with a parked `create_event`: one confirmation, with the conflict text on the item. A hard veto: no park, the call refused. Budget over the limit: one pause before any agent runs; deny ends the turn with nothing run.

**Acceptance Scenarios**:

1. **Given** a constraint-gated call that conflicts with a constraint needing the user's OK, **When** it parks, **Then** the item carries the conflict text and no other pause opens.
2. **Given** a tool that opted out but is constraint-gated (`draft_email`), **When** the veto says the user must OK it, **Then** the call parks with the conflict text.
3. **Given** a hard veto, **When** the call is made, **Then** it is refused and not parked, as today.
4. **Given** the turn's estimated spend is over budget, **When** the turn starts, **Then** Ze pauses once before execution; approve runs the turn normally (writes still park); deny ends the turn and nothing runs.
5. **Given** a workspace call the WorkspaceGate marks as needing approval, **When** it is called, **Then** it parks like any asks-first call and runs only after approval; a call the gate allows runs at once.

---

### User Story 7 - The intent-based gate is gone (Priority: P2)

Agents no longer declare intents or modes. The capabilities settings and REST surface are removed. The decision to ask lives only on the tool, so it is the same on every path, and an engineer adding a new IRREVERSIBLE tool gets a confirmation without doing anything.

**Why this priority**: Two gates would disagree. A pre-v1 hard cut removes the one that failed.

**Independent Test**: Search the code: no `Intent`, `Mode`, `intents`, `default_mode`, `_primary_intent`, `CapabilityGate`, `session_overrides`, `capability_overrides` references remain outside migrations. The capabilities REST routes return 404. A new test tool declared IRREVERSIBLE without `asks_first` parks when called.

**Acceptance Scenarios**:

1. **Given** the codebase after this phase, **When** searching for the deleted names, **Then** none remain outside migration history.
2. **Given** a database migrated to head, **When** inspecting tables, **Then** `capability_overrides` does not exist.
3. **Given** an agent class with `enabled = False`, **When** routing picks it, **Then** the turn is blocked, as today.
4. **Given** ze-web, **When** the user opens settings or chat, **Then** no UI reads or writes capabilities.
5. **Given** a tool declaring `asks_first=False` without a `no_ask_reason`, or a REVERSIBLE tool declaring `asks_first`, **When** the registry loads, **Then** registration fails with a clear error.

---

### User Story 8 - Evals prove the rule end to end (Priority: P3)

Eval scenarios cover "delete my 3pm", "send Ana the notes", a compound read + send, a deny, and a conductor delegation. Each asserts that a confirmation opened and that no asks-first tool ran before approval.

**Why this priority**: Unit tests prove the mechanism; evals prove the routed, real-model paths reach it.

**Independent Test**: Run the new eval scenarios against `make dev-eval`; all pass.

**Acceptance Scenarios**:

1. **Given** the eval harness, **When** the new scenarios run, **Then** each records an open confirmation with the expected item and zero asks-first tool executions before approval.
2. **Given** an approve step in the scenario, **When** it runs, **Then** the tool runs once and the reply reports it.

---

### Edge Cases

- **Several asks-first calls in one model response.** All are parked together; reads and reversible writes in the same response run; the loop stops after that response.
- **The same call parked twice in one turn** (two subtasks propose the identical email). *(Amended 2026-10-16 after the e2e run, Maestro-directed: showing both let one approve run the write twice.)* The confirmation shows one item per identical `(tool, args)`; each repeat takes that item's answer. On approve the call runs once; the repeat's loop gets a "not repeated" result and its trace call shows gate `duplicate` (never ran). On deny every copy is declined.
- **A parked loop's agent times out or errors on resume.** The approved call already ran; the error is reported as for any agent error; the trace keeps the executed call.
- **The approved call raises.** The loop resumes with the error as the tool result; the reply reports it; no automatic retry.
- **Nested parking deeper than one delegate level.** Delegation depth is capped today (`_DELEGATE_MAX_DEPTH`); the saved state holds one transcript per parked level, innermost first.
- **The user approves a confirmation that was already superseded or expired.** The reply is rejected as stale; nothing runs.
- **Two confirmations open on two threads.** Independent, keyed by `request_id` (113, 159).
- **Retry of a turn that parked.** Retry never parks; writes are refused (165). 180 already refuses to retry a reply that executed an irreversible action.
- **Streaming.** Tokens streamed before a park are shown; the confirmation follows; the resumed loop streams its reply as a new message.
- **Reconnect while a confirmation is open.** The open confirmation is replayed on connect, as today, with its items.
- **Agents that call a tool outside the shared loop** (the companion calls one tool directly). Asks-first tools may only be called through the shared loop or the delegate path; a direct call of an asks-first tool fails loudly (not silently runs).
- **Unattended hold that is never answered.** The hold expires after 24 hours and counts as a deny; the run continues per US5 scenario 4.
- **Quiet hours** (177). An unattended hold push is a push the user asked for; quiet hours do not delay it unless the 177 rules for that class already do.

## Requirements *(mandatory)*

### Functional Requirements

**The rule**

- **FR-001**: Every WRITE tool declaration MUST resolve to "asks first" or "runs". IRREVERSIBLE tools ask first by default. A tool MAY opt out only by declaring `asks_first=False` with a non-empty `no_ask_reason`. REVERSIBLE tools run and MUST NOT declare `asks_first` or `no_ask_reason`. READ tools MUST NOT declare either. Violations MUST fail registration.
- **FR-002**: A tool MAY declare a pre-call check that decides, from its arguments and context, whether this call asks first. The workspace tools MUST use this for the WorkspaceGate decision (action × origin). A pre-call check MUST NOT run the tool.
- **FR-003**: The phase MUST apply the audit table above: 12 tools ask, `pause_goal` and `resume_goal` become REVERSIBLE undo pairs, 16 opt out with the listed reasons, 5 workspace tools use the workspace check.
- **FR-004**: Whether a call asks first MUST depend only on the tool's declaration, its pre-call check and the 144 constraint veto, never on the agent, the route, or any intent.

**Park**

- **FR-005**: When a loop calls a tool that asks first, the tool MUST NOT run. The call MUST be recorded as a parked write with: tool name, exact arguments, effect phrase, a short argument summary for display, whether it is editable, any constraint conflict text, and the originating tool call id.
- **FR-006**: The loop that parked MUST stop after the current model response. Reads and runs-without-asking writes in that response MUST still run. Its transcript (messages so far, including the assistant tool-call message and the results of the calls that ran) MUST be saved in the conversation state.
- **FR-007**: When a specialist parks inside a delegate call, the conductor's loop MUST park behind that delegate call, and both transcripts MUST be saved, so that resuming the specialist yields the delegate result that resumes the conductor.
- **FR-008**: In a parallel fan-out, a parking subtask MUST return normally (not pause). Finished subtasks' results MUST be saved before the turn pauses. The pause MUST happen only after every subtask has finished or parked.
- **FR-009**: The turn MUST pause at a dedicated graph step whose state is saved to the checkpoint. No pause MAY be raised from inside a tool, a hook, a delegate call, or a parallel child task. The existing in-loop pause sites (workspace `ToolConfirmationRequired`, the constraint veto hook interrupt, the delegate gate interrupt) MUST be deleted.

**Confirm**

- **FR-010**: One confirmation MUST list every parked write of the pause, each with its effect phrase, argument summary, constraint conflict text if any, and an edit affordance if editable. Choices: approve all, deny all, and edit for editable items.
- **FR-011**: The confirmation MUST use the existing confirmation frame, reshaped (pre-v1 hard cut) to carry `items`, and the existing `pending_confirmations` storage keyed by `request_id`. Replay on reconnect, timeout and push-when-offline MUST work as today.
- **FR-012**: A turn MUST open at most 3 confirmations. A further asks-first call in the same turn MUST NOT run or park; the loop MUST get a refusal telling it to ask the user in its reply.

**Resume**

- **FR-013**: On approval, each approved call MUST run with exactly its parked arguments (or with only the user-edited field changed), before any further model call of its loop.
- **FR-014**: Each parked loop MUST then resume from its saved transcript, with each call's real result as the response to its original tool call id. A resumed loop MUST NOT be able to change, drop or repeat an approved call.
- **FR-015**: A resumed loop MAY park again; this opens a new confirmation with a new `request_id`, subject to FR-012.
- **FR-016**: Parked loops and finished subtasks MUST survive a server restart between pause and answer.
- **FR-017**: On deny or timeout, no parked call MUST run. Each parked loop MUST resume with a "the user declined; nothing was done" result for each denied call. The final reply MUST contain "Okay, I didn't <effect phrase>" for each denied item; code MUST add it when the model's reply does not.
- **FR-018**: A new turn that completes on the same thread MUST supersede an open confirmation: nothing parked runs and the parked state is discarded.
- **FR-019**: An answer to a superseded or expired confirmation MUST be rejected; nothing runs.

**Composition**

- **FR-020**: The 144 constraint veto MUST be evaluated when a constraint-gated call is made, before it parks or runs. A conflict that needs the user's OK MUST park the call (even if the tool opted out) with the conflict text on the item. A hard veto MUST refuse the call without parking.
- **FR-021**: The 113 spend budget check MUST run as its own pause before the turn executes. Approve runs the turn (writes still park). Deny ends the turn with nothing run. It MUST NOT be combined with write confirmations.
- **FR-022**: A retry turn MUST NOT park or open a confirmation; WRITE tools stay refused (165). Retry eligibility (165, 180) is unchanged.

**Unattended**

- **FR-023**: Workflow and goal plans MUST list, per step or milestone, the asks-first tools it may call. Approving the plan MUST pre-approve those tools for that step only, with any arguments (no argument limits in this phase).
- **FR-024**: Saving a workflow revision (108) that changes a step MUST clear that step's pre-approvals until the user approves the revision. A change made by Ze (agent tool) asks for that approval in the same confirmation. A change saved through the REST API clears them and returns the steps that need approval; the caller grants them explicitly (`approve_writes`).
- **FR-025**: In an unattended run (workflow step, goal executor, scheduled job), a pre-approved call MUST run without asking and MUST be recorded as run under pre-approval. A call that is not pre-approved MUST hold the run and send one push through the 177 governor as a push the user asked for. The user MUST be able to approve or deny from the notification or chat. Approve runs the exact held call and continues; deny, or no answer within 24 hours, continues with a "declined" result.

**Hard cut**

- **FR-026**: `Intent`, `Mode`, the agent `intents` attribute, `default_mode`, `_primary_intent`, `SubTask.intent`, `CapabilityGate`, `capability_overrides` (dropped by a migration), the `/api/v0/capabilities` routes, `session_overrides`, the draft-then-re-run confirmation path (`draft_response`, `await_confirmation` and their edges), the 152 per-delegate gate and the 158 per-subtask gates MUST be deleted. The agent `enabled` flag MUST stay and keep blocking disabled agents.
- **FR-027**: Any code that read the deleted names (the complexity estimator's intent argument, the delegate tool's `intent` argument, the trace's intent fields, ze-web's capabilities usage, the generated client) MUST be updated in the same change. The 155 mixed gather+act rewrite keeps working on a per-subtask "changes something" label from the decomposer, which is a routing label, not a gate.
- **FR-028**: The goal-local tool confirmation added on the 171 Follow-ups floor MUST be deleted and replaced by this mechanism.

**Observability**

- **FR-029**: The message trace MUST record, per parked write: tool, argument summary, outcome (approved, edited, denied, timed out, superseded, refused-over-cap, pre-approved), and the `request_id`. The trace panel MUST show them.
- **FR-030**: Each executed asks-first call MUST still produce its 135/136 action record, citing the approval.

### Key Entities

- **Parked write**: one asks-first call that did not run yet. Tool, exact arguments, effect phrase, argument summary, editable flag, constraint conflict text, originating tool call id, owning loop.
- **Parked loop**: a saved agent transcript stopped at a park, with the agent name, its context needed to resume (model, active skills, procedure scope), and, for a conductor, the delegate call it is waiting on.
- **Write confirmation**: one pause; `request_id`, its parked writes, status (open, approved, denied, timed out, superseded), round number within the turn.
- **Pre-approval**: on a workflow step or goal milestone, the set of asks-first tool names the user approved with the plan, cleared when the step changes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the eval scenarios "delete my 3pm", "send Ana the notes", the compound read + send and the conductor delegation, 100% open a confirmation and 0 asks-first tools run before approval.
- **SC-002**: In tests, every approved call runs exactly once with arguments identical to the parked ones (or to the user's edit), across single, compound, conductor and restart paths.
- **SC-003**: In a compound turn with N subtasks, each finished subtask's tools run exactly once in total, before and after the pause.
- **SC-004**: After a deny or a timeout, 0 parked calls run, and 100% of replies contain the "didn't" line for each denied item.
- **SC-005**: A user approving a turn sees one confirmation per pause, never one per tool call, and never a second confirmation for a constraint conflict on the same call.
- **SC-006**: A weekly workflow with a pre-approved email sends it without any confirmation over 4 simulated weeks; a non-pre-approved irreversible call holds the run and produces exactly 1 push.
- **SC-007**: After the phase, 0 references to the deleted gate names remain outside migration history, and adding a new IRREVERSIBLE tool with no other change makes it ask first.

## Assumptions

- The confirmation timeout stays `CONFIRM_TIMEOUT_SECONDS` (900 s by default) for interactive turns. Unattended holds wait 24 hours (user, C4).
- All agents that call tools do so through the shared agentic loop or the delegate path; the companion's one direct tool call is not an asks-first tool. The plan verifies this and makes a direct call of an asks-first tool fail loudly.
- The saved transcripts contain only plain messages and tool results; agent dependencies (clients, stores) are rebuilt on resume, not saved.
- The effect phrases declared in 165 are good enough for display; the argument summary comes from the tool's declared describe function where one exists (the 144 `constraint_describe`) or from a generic summary of its arguments.
- The eval harness cannot answer a confirmation today; this phase adds an eval confirm step (plan R10).
- The 171 Follow-ups floor's goal fix is on `main` before implementation starts; if not, the first task re-reads its diff.
- Per-tool user preferences ("stop asking me for create_event") are out of scope and may follow in a later phase.
