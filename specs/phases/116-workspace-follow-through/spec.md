# Feature Specification: Workspace Follow-Through

**Feature Branch**: `116-workspace-follow-through`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Specify the sibling to Phase 115 Workspace Environment: detached runs and follow-through. Destination UX from 115 clarification: wait-then-detach (Cursor-like). Short workspace runs finish on the same conversation turn. Longer runs continue after the turn ends. When a detached run finishes, Ze starts an automatic follow-up turn on that same thread. If the client is offline, Ze also sends a push notification. User can cancel a running detached run. Only one workspace run at a time (busy). Do not rewrite conversations to be generally async — reuse starting a turn and notifying, the same way other background work already talks to the user. Do not re-specify the workspace computer (files, shell, isolation, modes) — that is 115. This spec attaches to 115's durable workspace-run records."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Short work stays in the turn; long work lets go (Priority: P1)

A user asks Ze to run a command or skill script. If it finishes quickly, the result is on that same reply — no extra ceremony. If it is still going after a short wait, the reply says the work is still running and the turn ends. The run continues in the workspace. The user is not stuck watching a spinner for minutes.

**Why this priority**: This is the Cursor-like feel. Without it, every long script blocks the conversation (Phase 115's in-turn-only behavior).

**Independent Test**: Can be fully tested with a command that finishes immediately (result on the same turn) and a command that runs longer than the wait (turn ends with “still running,” run record stays in progress, files may appear later).

**Acceptance Scenarios**:

1. **Given** a workspace command that finishes within the short wait, **When** the user asked for it in a conversation, **Then** the result (success or failure, output preview, files) is on that same turn and no follow-up turn is started for that run.
2. **Given** a workspace command that is still running after the short wait, **When** the turn would otherwise keep blocking, **Then** the reply states that the work is still running, the turn ends, and the workspace-run record remains in progress.
3. **Given** a detached run, **When** the user looks at that conversation, **Then** they can see that work is still running and which run it is, without guessing.
4. **Given** workspace mode is Plan or Off, **When** the user asks for computer work, **Then** nothing is detached (nothing ran).
5. **Given** workspace mode is Ask or Auto-edit, **When** a command still needs confirmation, **Then** detach happens only after the user approves (or not at all if they deny).

---

### User Story 2 - When it finishes, Ze comes back on that thread (Priority: P1)

A detached run finishes (success, failure, or time budget). Ze starts a follow-up on the **same conversation** — as if the user had asked “what happened?” — and uses the run’s result (output, files) to continue. The user does not have to poll.

If the chat app is not connected, Ze also sends a push notification so the user knows to come back. If the app is connected, the follow-up in the thread is enough; a completion push is not required.

**Why this priority**: Detach without coming back is a job board, not an assistant. This is the auto follow-up locked in the 115 clarification.

**Independent Test**: Can be fully tested by starting a long run, waiting until it finishes with the app connected (follow-up appears on that thread, no push required), then repeating with the app disconnected (follow-up is waiting in the thread and a push was sent).

**Acceptance Scenarios**:

1. **Given** a detached run that succeeds, **When** it finishes, **Then** Ze starts a follow-up on the same conversation that can see the result and any files the run produced.
2. **Given** a detached run that fails or hits the time budget, **When** it finishes, **Then** the follow-up tells the user it failed or ran too long, in plain language, and any partial files remain inspectable.
3. **Given** the chat app is connected, **When** a detached run finishes, **Then** the follow-up appears in the thread and Ze MUST NOT also send a completion push for that run.
4. **Given** the chat app is not connected, **When** a detached run finishes, **Then** Ze sends a push notification about that run and the follow-up is available on the thread when the user returns.
5. **Given** a run that finished on the same turn (never detached), **When** that turn completes, **Then** Ze MUST NOT start a follow-up turn and MUST NOT send a completion push for that run.
6. **Given** a follow-up would start while another turn is already in progress on that conversation, **When** the run finishes, **Then** Ze waits until that in-progress turn ends, then starts the follow-up — it does not interrupt mid-reply.

---

### User Story 3 - Stop work that has let go (Priority: P1)

The user started something that detached. They want it to stop — wrong command, taking too long, changed their mind. They can cancel that run. The workspace is left as it is (partial files remain). Ze does not pretend the run succeeded.

**Why this priority**: A background run with no stop is a trap. Resetting the whole workspace is too blunt.

**Independent Test**: Can be fully tested by starting a long run, cancelling it, confirming the run record is cancelled, later files from that run stop appearing, and a follow-up (or the same-turn message) tells the user it was stopped.

**Acceptance Scenarios**:

1. **Given** a detached run in progress, **When** the user cancels it, **Then** the run stops, its status is cancelled, and it does not keep writing.
2. **Given** the user cancels, **When** follow-through runs, **Then** Ze tells them it was stopped and does not treat it as success.
3. **Given** a run that already finished, **When** the user tries to cancel it, **Then** nothing is killed; they are told it already finished.
4. **Given** the user cancels, **When** they have not been asked to confirm cancel, **Then** cancel still happens — stopping a run they started does not require a second confirmation. Reset of the whole workspace still requires confirmation (Phase 115).

---

### User Story 4 - One thing at a time (Priority: P2)

While a detached run is in progress, the user asks Ze to run something else in the workspace. Ze does not start a second run that silently interleaves. The user is told the workspace is busy, what is running, and that they can cancel it or wait.

**Why this priority**: Phase 115 already forbids silent interleaving. Detach makes that visible: the user can talk while work continues, so the busy rule must be explicit.

**Independent Test**: Can be fully tested by leaving a long run detached, asking for another command, and confirming the second command did not start; then cancelling or waiting until the first finishes and confirming a new command can start.

**Acceptance Scenarios**:

1. **Given** a detached run in progress, **When** the user asks Ze to start another workspace command or script, **Then** the second run does not start and the user is told what is already running.
2. **Given** a detached run in progress, **When** unattended work would also need the workspace, **Then** it does not start a second run (it skips or waits; it must not interleave).
3. **Given** the in-progress run has finished or been cancelled, **When** the user asks for a new command, **Then** it may start (subject to workspace mode).

---

### Edge Cases

- What happens if the run finishes in the same instant the turn is detaching? Treat it as same-turn completion: result on that turn, no follow-up, no completion push.
- What happens if the user sends a new message on that thread while a run is detached? The new message is a normal turn. It MUST NOT start a second workspace run (User Story 4). The follow-up still happens after the run finishes (and after any in-progress turn, per User Story 2).
- What happens if the user starts a different conversation while a run is detached? The follow-up still goes to the conversation that started the run, not the new one.
- What happens if the workspace becomes unavailable after detach? The run fails. Follow-through reports failure. No fabricated success.
- What happens if follow-up itself would run another long command? Same wait-then-detach rules apply. The one-run busy rule still holds.
- What happens if the user switched workspace mode to Off or Plan while a run is detached? The in-flight run is not silently upgraded or rewritten; cancel remains available. New runs follow the new mode.
- What happens if push delivery fails while the user is offline? The follow-up is still on the thread when they return. Ze does not retry forever; missing a push is not treated as a failed run.
- What happens on reset while a detached run is in progress? Phase 115 already requires reset not to leave a run writing into an emptied workspace without telling the user — stop or wait, then reset.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST wait a short time for a conversational workspace run to finish inside the turn. If it finishes in time, the result belongs on that turn (Phase 115 in-turn outcome).
- **FR-002**: If the run is still in progress after that short wait, the system MUST end the turn with a clear “still running” outcome, keep the workspace-run record in progress, and let the run continue.
- **FR-003**: System MUST NOT rewrite conversations into a generally async session. Follow-through MUST be a normal follow-up turn on the same conversation, plus a push when the client is offline.
- **FR-004**: When a detached run reaches a terminal status (succeeded, failed, timed out, cancelled), the system MUST start a follow-up turn on the conversation that started the run, with access to that run’s result and files.
- **FR-005**: System MUST NOT start a follow-up turn or send a completion push for a run that finished inside the originating turn.
- **FR-006**: If the chat client is connected when a detached run becomes terminal, the system MUST deliver the follow-up in the thread and MUST NOT send a completion push for that run.
- **FR-007**: If the chat client is not connected when a detached run becomes terminal, the system MUST send a push notification about that run in addition to leaving the follow-up on the thread.
- **FR-008**: Follow-up MUST wait for any in-progress turn on that conversation to finish before starting; it MUST NOT interrupt a reply in flight.
- **FR-009**: Users MUST be able to cancel a detached run that is still in progress, without a second confirmation. Cancelled runs MUST stop doing work and MUST NOT be reported as success.
- **FR-010**: System MUST show an in-progress detached run to the user (in the conversation and in the workspace view) with enough identity to cancel the right one.
- **FR-011**: While a workspace run is in progress (in-turn or detached), the system MUST NOT start another workspace run. A second request is refused or told to wait, with a pointer to the running work. Silent interleaving is forbidden.
- **FR-012**: Detach and follow-through MUST attach to Phase 115 workspace-run records (stable identity, conversation, status, files touched). This spec MUST NOT change workspace isolation, credentials rules, network rules, or file storage.
- **FR-013**: Workspace execution modes from Phase 115 still apply. Detach MAY occur only for a run that was actually allowed to start. Off and Plan never detach. Ask and Auto-edit detach only after any required confirmation.
- **FR-014**: The Phase 115 time budget still stops a run that runs too long, including after detach. Hitting that budget is a terminal failure and gets follow-through like any other failure.
- **FR-015**: Unattended workspace work (Phase 115 User Story 4) MUST obey the one-run busy rule. Completing unattended work that was not started from a conversation MUST NOT invent a chat thread; it MAY notify using existing unattended-notification behavior and MUST NOT use this spec’s conversation follow-up path.
- **FR-016**: This spec MUST NOT implement the workspace computer (creating the environment, shell, files, skill-script storage, mode switching UI beyond showing a running run). Those remain Phase 115.
- **FR-017**: The short in-turn wait is a small fraction of the run time budget: long enough that ordinary quick commands finish in the turn, short enough that the user is not stuck. The exact durations are configuration chosen at plan time.

### Key Entities *(include if feature involves data)*

- **Workspace run** (from Phase 115, extended here): gains a live in-progress meaning after the originating turn has ended; terminal statuses drive follow-through. Still one durable record per execution.
- **Follow-up turn**: A normal conversation turn Ze starts when a detached run becomes terminal, on the same conversation that started the run, with that run’s result in view.
- **Completion push**: A push notification sent only when a detached run becomes terminal and the chat client is not connected.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A command that finishes in under the short wait returns its result on the same turn 100% of the time; no follow-up turn and no completion push for that run.
- **SC-002**: A command still running after the short wait leaves the user able to send another message in that conversation in under 5 seconds of the turn ending, while the run continues.
- **SC-003**: 100% of detached runs that reach a terminal status produce a follow-up on the originating conversation; zero silent finishes.
- **SC-004**: When the chat app is disconnected, 100% of those terminal detached runs also result in a push; when it is connected, 0% result in a completion push.
- **SC-005**: A user can cancel an in-progress detached run in under 15 seconds from deciding to stop; the run does not continue afterward.
- **SC-006**: 0 cases of two workspace runs executing at the same time.

## Assumptions

- Phase 115 (Workspace Environment) is specified and will exist: one durable isolated workspace, run records, execution modes, in-turn execution for runs that finish quickly, time budget, storage ceiling, skill-script rules. This spec does not re-decide those.
- Exact short-wait and time-budget numbers are plan-time configuration (FR-017). The short wait is tens of seconds, not minutes; the time budget remains minutes-scale as in Phase 115.
- Follow-up is a normal turn, not a live terminal stream of every output line. Streaming a full console UI is out of scope.
- Push uses Ze's existing notification path (the same family of alerts as other proactive messages). This spec does not add a new notification product.
- “Client connected” means the user's chat app has a live connection; if it does not, they are offline for FR-007.
- Cancel is user-initiated stop of one run, not workspace reset.
- One run at a time is a hard busy rule, not a queue of many commands (no backlog of detached work in this phase).
- This spec does not move Ze onto the desktop, does not add GUI computer-use, and does not give the workspace the user's personal files.
