# Feature Specification: Workspace Run Journal

**Feature Branch**: `129-workspace-run-journal`

**Created**: 2026-09-14

**Status**: Implemented

**Input**: User description: "Spec the workspace work we decided after comparing Ze's
workspace to Cloudflare Computer: the computer owns the in-flight run, not the HTTP
request that started it. Keep the existing always-on sidecar (Fly volume, unprivileged
subprocess, WorkspaceGate, skill-script approval). Adopt run handles and reattach —
start returns an id immediately; watch streams stdout/stderr/exit; reattach after a
mind restart recovers status, exit code, preview, and files touched; cancel is keyed
by that handle. Do not adopt Durable Objects, FUSE, just-bash, Worker isolates, SQLite
as the filesystem, named egress, or host-side git. Streaming to the chat UI is a later
layer on the same contract. Also close Phase 116's leftover one-run busy rule for
detached work."

**Governed by**: [`specs/phases/115-workspace-sidecar/spec.md`](../115-workspace-sidecar/spec.md)
(the computer: isolation, modes, files, skill scripts — unchanged) and
[`specs/phases/116-workspace-follow-through/spec.md`](../116-workspace-follow-through/spec.md)
(wait-then-detach, follow-up turn, push when offline). This phase changes the computer's
**run contract** so follow-through can reattach after the mind restarts; it MUST NOT
re-specify isolation, credentials, network policy, file storage, or conversation
async-ness. Named egress, isolate backends, and replacing the sidecar with Cloudflare
Computer are explicitly out of scope.

---

## Overview

Phase 115 gave Ze a durable isolated computer. Phase 116 taught conversational runs to
let go: a short wait, then the turn ends while the command continues, and Ze comes back
on that thread when it finishes. The missing piece is on the computer itself. Starting a
command is still one blocking request. If the mind restarts while a command is running,
follow-through can only see that the computer is busy. The output, exit code, and files
touched from that run are gone. That hole is already documented in production as a
tolerated loss.

This phase makes the **computer** the source of truth for a live command — the same idea
Cloudflare Computer's `exec` / `getExec` / `killExec` / event stream, without adopting
that platform. Ze starts a run, receives a stable handle, and can reattach, watch, or
stop that handle until it disposes it. The mind (FastAPI on Fly), the volume at
`/workspace`, and the unprivileged subprocess stay exactly where they are.

Live output in chat is allowed as a later layer on this same contract. A full terminal
console is not. Named network policies, host-side git, and a cheap isolate runtime stay
for later specs.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A run survives the mind restarting (Priority: P1)

The user asks Ze to run a command that takes longer than the short wait. The turn ends
with "still running." While it is still going, Ze's mind process restarts (deploy,
crash, `make dev` reload). When the command finishes, Ze still comes back on that
thread with the real result: what it printed, whether it succeeded, and which files it
touched — not a placeholder that says the output was lost.

**Why this priority**: This is the hole Phase 116 already named. Without it, detach is
only reliable while the mind stays up. Everything else in this spec (watch, cancel by
handle) is the same contract.

**Independent Test**: Start a command that outlives the short wait, restart the mind
while it is still running, wait until it finishes, and confirm the follow-up on that
conversation carries the real exit, a real output preview, and the files it produced.

**Acceptance Scenarios**:

1. **Given** a detached workspace run still in progress, **When** the mind restarts and
   the command later finishes, **Then** follow-through on the originating conversation
   includes the real exit status, output preview, and files touched — not an
   "output unavailable" placeholder.
2. **Given** a detached run that already finished during the restart window, **When**
   the mind comes back, **Then** it can still read that run's terminal result from the
   computer and start the same follow-up as if it had been watching all along.
3. **Given** the computer itself restarted and lost the in-flight process, **When** the
   mind reattaches, **Then** the run is marked failed in plain language (the command
   did not complete); Ze does not invent a successful result.
4. **Given** a run that finished inside the originating turn (never detached), **When**
   nothing restarts, **Then** behavior is unchanged from Phase 116: result on that
   turn, no follow-up, no completion push.

---

### User Story 2 - The user can watch a run that has let go (Priority: P2)

A command has detached. The user is not stuck in the originating turn, but they can
still see that the run is alive and what it is printing, without waiting for the
follow-up. Output arrives as it happens (stdout, then stderr, then exit) — not only as
a preview at the end.

**Why this priority**: Same contract as reattach (a handle you can watch). User-visible
value once the computer owns the run. Not required for the MVP if User Story 1 works;
the event stream on the computer MUST exist either way so reattach has something to
read.

**Independent Test**: Detach a long command that prints several lines over time. While
it is still running, open the conversation or workspace view and confirm new output
appears before the command exits; after exit, the follow-up still happens once.

**Acceptance Scenarios**:

1. **Given** a detached run that is printing output, **When** the user looks at that
   run, **Then** they see output that has already been produced, and later lines appear
   without waiting for the whole command to finish.
2. **Given** a run that has already exited, **When** the user (or the mind after
   restart) reads the handle, **Then** they get the buffered stdout/stderr and the
   exit event — watching after the fact still works.
3. **Given** Phase 116 follow-through, **When** live output was shown during the run,
   **Then** the follow-up turn still starts exactly once when the run becomes
   terminal; live watching does not replace follow-through and does not send a
   completion push while the client is connected.

---

### User Story 3 - Stop the right run by its handle (Priority: P2)

The user started a long command, changed their mind, and wants it stopped. They cancel
**that** run by its identity. A later run is not cancelled by accident. Cancel still
does not require a second confirmation (Phase 116). Reset of the whole workspace still
does.

**Why this priority**: Phase 116 already has cancel of "whatever is busy." Handles make
that identity explicit, which User Story 1 needs anyway.

**Independent Test**: Start a detached run, cancel it by the handle shown to the user,
confirm it stops and is reported as cancelled, and confirm a subsequent new command
can start.

**Acceptance Scenarios**:

1. **Given** a detached run in progress with a visible handle, **When** the user
   cancels that handle, **Then** the process stops, the run is cancelled, partial
   files remain inspectable, and follow-through tells them it was stopped.
2. **Given** no run in progress, **When** the user cancels a handle, **Then** nothing
   is killed; they are told that run is not running.
3. **Given** a run that already finished, **When** the user cancels its handle, **Then**
   nothing is killed; they are told it already finished.

---

### User Story 4 - One command at a time, even after detach (Priority: P2)

While a detached run is in progress, the user (or unattended work) asks Ze to run
something else. Ze does not start a second command that interleaves. The refusal names
the running command and its handle. This is Phase 116 User Story 4, which the
follow-through implementation left unfinished; this phase closes it on the new handle
contract.

**Why this priority**: Silent interleaving was already forbidden. Detach made it
user-visible. Handles make the busy signal a named run rather than a boolean.

**Independent Test**: Leave a long run detached, ask for another command, confirm the
second does not start and the message names what is already running; cancel or wait,
then confirm a new command can start.

**Acceptance Scenarios**:

1. **Given** a detached run in progress, **When** the user asks Ze to start another
   workspace command or skill script, **Then** the second run does not start and the
   user is told the handle and command that is already running.
2. **Given** a detached run in progress, **When** unattended work would also need the
   computer, **Then** it does not start a second run (it skips or waits).
3. **Given** the in-progress run has finished or been cancelled, **When** the user
   asks for a new command, **Then** it may start (subject to workspace mode).

---

### Edge Cases

- What happens if the run finishes in the same instant the turn is detaching? Treat it
  as same-turn completion (Phase 116): result on that turn, no follow-up, no completion
  push.
- What happens if the mind restarts twice while a run is still going? Each startup
  reattaches to the same handle; follow-through still fires once when the run becomes
  terminal.
- What happens if the computer is unreachable after restart? The run fails in plain
  language. Ze does not invent success. Existing files stay as they are.
- What happens if output is very large? Same as Phase 115: truncated preview, full
  output spilled to a workspace file. The stream MUST NOT dump an unbounded wall of
  text into chat.
- What happens on workspace reset while a handle is live? Phase 115 already requires
  reset not to leave a run writing into an emptied workspace — stop or wait, then
  reset. Cancel is by that handle.
- What happens if the user switches workspace mode to Off or Plan while a run is
  detached? The in-flight run is not rewritten; cancel remains available. New runs
  follow the new mode.
- What happens if two clients try to watch the same handle? Both MAY read it. There is
  still only one process.
- How does the system handle a handle the computer has already disposed? Treated as
  unknown: not running, no fabricated output.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Starting a workspace command MUST return a stable run handle immediately
  and MUST NOT require the caller to hold the original start request open until the
  process exits.
- **FR-002**: The computer MUST be the source of truth for an in-flight run: status,
  output produced so far, exit code once known, timed-out flag, and files touched.
- **FR-003**: After the mind restarts, the system MUST reattach to every still-open
  handle and recover that run's real result for Phase 116 follow-through. A restart
  MUST NOT be sufficient cause to replace the result with an "output unavailable"
  placeholder when the computer still has the run.
- **FR-004**: Callers MUST be able to read a handle after the process has exited and
  still receive status, exit code, output preview, and files touched, until the handle
  is disposed or expires under the retention assumption below.
- **FR-005**: Callers MUST be able to watch a handle as a sequence of stdout, stderr,
  and exit events (live while running; replayed after exit).
- **FR-006**: Cancel MUST target a specific handle. Cancel of a live handle stops that
  process. Cancel of a missing or already-terminal handle MUST NOT kill a different
  run.
- **FR-007**: While any handle is still running, the system MUST NOT start another
  workspace command or skill script. The refusal MUST name the running handle and
  command. This applies to conversation, user-initiated, and unattended origins.
- **FR-008**: Phase 116 follow-through, confirmation, workspace modes, isolation,
  credentials stripping, public-internet-only egress, storage ceiling, time budget,
  and skill-script executable approval MUST remain in force. This spec MUST NOT
  change them except where a handle replaces "the currently busy process" as the
  identity of a run.
- **FR-009**: This spec MUST NOT relocate the computer onto Cloudflare Durable
  Objects, a FUSE-mounted virtual filesystem, just-bash, a Worker isolate, or any
  other Cloudflare Computer backend. The always-on sidecar with a real volume and an
  unprivileged subprocess remains the computer.
- **FR-010**: This spec MUST NOT add named egress policies, host-side git or asset
  publishing, or a second execution backend. Those are later, separate specs.
- **FR-011**: Live watching MUST NOT replace follow-through. A detached run that
  becomes terminal still starts exactly one follow-up on the originating conversation
  (and a completion push only when the client is offline), as Phase 116 requires.
- **FR-012**: Shown output MUST still pass Phase 115 secret redaction. Handles, event
  streams, and recovered previews MUST NOT leak Ze credentials.

### Key Entities

- **Run handle**: Stable identity of one execution on the computer, returned at
  start, used to watch, reattach, and cancel. Distinct from the conversation message
  that requested the work.
- **Run journal**: The computer's retained record for that handle — in progress or
  terminal — including output events, exit, and files touched. This is what the mind
  reads after a restart.
- **Workspace run** (Phase 115/116): The mind's durable record in Ze, still one row
  per execution, now keyed to the computer's handle so follow-through can reattach.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tests where the mind restarts during a detached run and the
  computer kept the process, the follow-up carries the real exit and a real output
  preview (not a lost-output placeholder).
- **SC-002**: A user looking at a live detached run sees output that was produced at
  least 5 seconds before the command exits, for a command that prints throughout its
  run.
- **SC-003**: Cancel of a named in-progress handle takes effect in under 15 seconds;
  that process does not continue afterward.
- **SC-004**: 0 cases of two workspace commands executing at the same time, including
  when the first run has already detached from its originating turn.
- **SC-005**: A run that finishes inside the short wait still returns on that same
  turn 100% of the time (Phase 116 SC-001 preserved).

## Assumptions

- Phase 115 and Phase 116 exist and stay the product: one workspace, wait-then-detach,
  follow-up turn, push when offline, modes, isolation. This phase only changes how a
  live command is addressed and recovered.
- The computer keeps a terminal journal long enough that a mind restart during or
  just after the process can still read it (at least until Ze has persisted the
  result onto the Phase 115 workspace-run record). Exact retention is a plan-time
  choice.
- Live watching in chat is a growing output preview on the existing still-running
  chip / workspace view, not a full terminal emulator. Phase 116's "not a live
  console UI" still holds for a dedicated terminal product.
- Event streams are the same contract Cloudflare Computer uses (`stdout` / `stderr` /
  `exit`); Ze copies the handle idea, not the Durable Object, FUSE sync, or isolate
  backends.
- One run at a time remains a hard busy rule, not a queue.
- Named egress (`none` vs public) is a later spec, as decided in the Cloudflare
  comparison. Public-internet-only from Phase 115 remains the network bar.

## Verbatim Constraints

These identifiers are pinned by the comparison that scoped this phase and MUST appear
on the computer's control surface as written:

- `POST /run` — start; MUST return `{ id }` immediately; the process keeps running
- `GET /runs/{id}` — status, exit code, preview, files touched
- `GET /runs/{id}/events` — stream of stdout, stderr, and exit
- `POST /runs/{id}/cancel` — stop that handle
- `/workspace` — workspace root on the computer (unchanged from Phase 115)
- `WorkspaceGate` — mode × action × origin gate (unchanged)
- `workspace_run_skill_script` — skill-script entry (unchanged; runs still get a handle)

## Out of Scope

- Replacing the sidecar with Cloudflare Computer, Durable Objects, `@cloudflare/dofs`,
  `computerd` FUSE, just-bash, or Worker JavaScript isolates
- SQLite (or any VFS) as the filesystem; the Fly/Docker volume remains file truth
- Named egress policies, host-side git, asset publishing, Code Mode / long-context JS
- Replacing `workspace_*` tools or `WorkspaceGate` with an AI SDK tool pack
- GUI computer-use, desktop-local files, moving the mind off Fly/FastAPI
- Phase 116 follow-through product (already specified); this phase only makes it
  restart-safe
