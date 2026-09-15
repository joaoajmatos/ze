# Feature Specification: Workspace Live Output

**Feature Branch**: `131-workspace-live-output`

**Created**: 2026-09-14

**Status**: Implemented

**Input**: User description: "Spec the later layer Phase 129 deferred: live workspace
output in chat. 129 made the computer own the run and exposed a watch stream for
stdout, stderr, and exit. Chat still only shows a still-running chip; the workspace
page lists and cancels runs but does not show unfolding output. Stream live printed
output onto the existing still-running chip and the workspace run banner. Replay
already-produced lines if the user opens the thread or workspace view mid-run. Do
not replace follow-through, do not add a terminal emulator, do not change isolation,
modes, or the run contract."

**Governed by**: [`specs/phases/129-workspace-run-journal/spec.md`](../129-workspace-run-journal/spec.md)
(the computer owns the handle and the event stream — this phase is the user-visible
layer on that same contract) and
[`specs/phases/116-workspace-follow-through/spec.md`](../116-workspace-follow-through/spec.md)
(wait-then-detach, follow-up turn, push when offline). This phase MUST NOT re-specify
the computer, isolation, credentials, network policy, file storage, or conversation
async-ness. Named egress, isolate backends, and a full terminal console remain out of
scope.

---

## Overview

Phase 129 taught the computer to keep a live run: start returns a handle, the mind can
reattach after a restart, and a watch stream already exists. The person using Ze cannot
see that stream. A detached command still looks like a static "still running" label
until the follow-up turn arrives.

This phase is the missing screen, not a new computer. While a command is detached, the
conversation the user already has open grows with what the command has printed so far,
and the workspace view shows the same unfolding output. When the command finishes, Ze
still comes back on that thread exactly once — live watching does not replace
follow-through and does not become a second completion channel.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See what a detached command is printing in the conversation (Priority: P1)

The user asked Ze to run something that outlived the short wait. The turn ended with
"still running." They stay in that conversation. New lines the command prints appear
there before the command finishes — a growing preview, not a blank wait and not a
full console. Secrets stay redacted the same way command output already is.

**Why this priority**: This is the deferred user-visible half of Phase 129. Without it,
owning the run only helps the mind; the person still stares at a static chip.

**Independent Test**: Detach a command that prints several lines over time. Stay on
that conversation. Confirm new printed output is visible at least several seconds
before the command exits, then confirm the follow-up still happens exactly once.

**Acceptance Scenarios**:

1. **Given** a detached run that is still printing, **When** the user looks at that
   conversation, **Then** they see output that has already been produced, and later
   lines appear without waiting for the whole command to finish.
2. **Given** the user opens or returns to that conversation after the run has already
   printed some lines, **When** they look at the still-running indicator, **Then** they
   see those earlier lines immediately and then any new lines.
3. **Given** live output was shown during the run, **When** the command becomes
   terminal, **Then** the follow-up on that thread still starts exactly once; watching
   does not suppress it, duplicate it, or send a completion push while the client is
   connected.

---

### User Story 2 - See the same unfolding output on the workspace page (Priority: P2)

The user leaves chat and opens the workspace view because they want to inspect files
or stop the run. The in-progress run they already know about is still named there, and
it shows the same growing preview as the conversation — not a second, contradictory
story of what the command printed.

**Why this priority**: The workspace page is the other place a live run is already
visible. Showing output only in chat would split the truth.

**Independent Test**: Start a detached printing command, open the workspace view while
it is still running, confirm the in-progress run shows unfolding output, cancel or wait
until it finishes, and confirm the preview matches what the conversation showed.

**Acceptance Scenarios**:

1. **Given** a detached run in progress, **When** the user opens the workspace view,
   **Then** the in-progress run shows output already produced and continues to grow.
2. **Given** the same run is visible in both the conversation and the workspace view,
   **When** a new line is printed, **Then** both places show that line; they do not
   disagree on what has been printed so far.
3. **Given** the user stops the run from the workspace view, **When** cancel takes
   effect, **Then** live output stops growing and follow-through still reports that
   the run was stopped.

---

### Edge Cases

- What happens when output is very large? The user sees a truncated preview (same
  order of size as existing command-output previews). The rest remains retrievable as
  a workspace file rather than a wall of text in chat.
- What happens if the client disconnects and reconnects mid-run? They see already-
  produced lines again (replay), then new lines. They do not see a duplicate dump of
  the same prefix stacked twice as if it were new.
- What happens if the run finishes while they are watching? Growth stops on the exit
  line. The follow-up still fires once. The still-running indicator is no longer
  shown as in-progress.
- What happens if the computer or the watch stream is unavailable? The still-running
  indicator remains honest (the run is still going if the mind knows that). The user
  is not shown invented output. Follow-through still uses Phase 129 reattach.
- What happens with binary or non-text output? Chat does not dump binary. The user
  sees a short note that output is not printable, and can retrieve the file from the
  workspace.
- What happens with secrets in printed output? Shown lines pass the same redaction
  already required of command previews. Credentials are not displayed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: While a workspace run is detached and still in progress, the
  conversation that started it MUST show a growing preview of what the command has
  printed so far (standard output, then error output) before the command exits.
- **FR-002**: Opening or returning to that conversation mid-run MUST replay
  already-produced printable lines immediately, then continue with new lines.
- **FR-003**: The workspace view's in-progress run MUST show the same unfolding
  preview as the conversation for that handle — one truth, two places.
- **FR-004**: Live watching MUST NOT replace follow-through. A detached run that
  becomes terminal MUST still start exactly one follow-up on the originating
  conversation. Watching MUST NOT send a completion push while the client is
  connected.
- **FR-005**: Shown live output MUST stay bounded: a truncated preview, with any
  remainder available as a workspace file, matching the existing preview-size
  discipline for command output.
- **FR-006**: Shown live output MUST pass the existing command-output redaction.
  Ze credentials MUST NOT appear in the conversation or the workspace view.
- **FR-007**: This spec MUST NOT change isolation, workspace modes, skill-script
  executable approval, the one-run busy rule, or the computer's run contract
  (start returns a handle; watch, reattach, and cancel are already specified).
- **FR-008**: This spec MUST NOT add a full terminal emulator, a second execution
  backend, named egress, or a new completion channel besides existing follow-through.
- **FR-009**: Cancel from the workspace view during live watching MUST stop that
  handle (Phase 116/129 cancel rules unchanged) and MUST stop the preview from
  growing further.
- **FR-010**: If the watch stream cannot be read, the system MUST keep the
  still-running state honest and MUST NOT invent printed output.

### Key Entities

- **Run handle**: Stable identity of one execution on the computer (Phase 129). This
  phase only displays that handle's live printed output; it does not mint a new
  identity.
- **Live output preview**: The bounded, redacted unfolding text the user sees while
  a handle is in progress. Distinct from the terminal preview persisted on the
  follow-up, though the two MUST not contradict what was printed.
- **Still-running indicator**: The existing conversation marker that a detached run
  is in progress. This phase adds growing output to it; it remains the in-progress
  marker, not a console.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a detached command that prints throughout its run, a user looking
  at that conversation sees printed output that was produced at least 5 seconds
  before the command exits, in 100% of such test runs.
- **SC-002**: Opening the workspace view during the same run shows that same
  already-produced output in 100% of test runs, and a later line appears in both
  places.
- **SC-003**: In 100% of test runs where live output was shown, exactly one
  follow-up starts when the run becomes terminal, and no extra completion push is
  sent while the client is connected.
- **SC-004**: 0 shown live-output samples contain credential-shaped secrets that
  existing command-output redaction would have removed from a final preview.

## Assumptions

- Phase 129 is implemented: the computer retains the journal and a watch stream
  already exists for the mind to read. This phase is display, replay, and the
  rule that watching does not replace follow-through.
- Live watching is a growing preview on the existing still-running conversation
  marker and the existing workspace in-progress banner — not a dedicated terminal
  product. Phase 116's "not a live console UI" still holds for a full console.
- Preview size and redaction reuse Phase 115/129 defaults. No new retention of
  printed lines beyond what the computer already keeps for reattach.
- One run at a time remains a hard busy rule. This phase does not queue output
  from a second command.
- The user is the single operator (single-user model). There is no multi-viewer
  permission model.

## Verbatim Constraints

- `workspace-still-running-chip` — existing conversation still-running marker;
  live output attaches here, not a new parallel chip
- `running-run-banner` — existing workspace in-progress banner; live output
  attaches here
- `/workspace` — workspace page (unchanged route)
- `GET /api/v0/workspace/runs/{id}/events` — existing watch stream from Phase 129;
  this phase consumes it, it MUST NOT invent a second event contract
- stdout / stderr / exit — event kinds already specified in Phase 129; live
  display MUST use this sequence

## Out of Scope

- Re-specifying the computer, isolation, modes, skill scripts, or follow-through
  product
- A full terminal emulator or interactive stdin console
- Named egress, host-side git, isolate backends, Cloudflare Computer
- Changing cancel confirmation rules (cancel still does not require a second
  confirmation; reset still does)
- Streaming token-level assistant replies (already a different path)
