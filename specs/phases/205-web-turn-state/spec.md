# Feature Specification: Web Turn State — One Owner per Thread

**Feature Branch**: `205-web-turn-state`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 198 (audit bug floor: B10, a background thread's attention dot overwritten after a confirmation, is fixed there as a regression test plus a minimal fix; this phase removes the cause)

**Can run in parallel with**: 206 (disjoint files: 205 owns `entities/conversation`, `features/turn-stream`, `features/respond-to-confirmation/ui`, `features/trace-state/ui`, `entities/presence`, `widgets/sessions-rail`, `shared/api/ws-client.ts`; 206 owns `shared/lib/query-keys.ts`, `shared/api` query adapter, `entities/*/api`, `features/invalidate-on-ws-refresh`). The one shared file is `features/retry-reply/model/useRetryReply.ts`: 205 changes its running check (line 24) and 206 its invalidation keys (lines 34-35). Land 206's edit after 205, or let one lane own the file.

**Input**: Architecture review 2026-10-22, candidate C18 ("entities/conversation owns all per-thread turn state"). Report: `architecture-review-2026-10-22.html`; floor brief `floor-briefs-2026-10-22.md`, Wave 1.

**Governed by**: phase 187 (one state owner per frame, `frame-registry.ts`), `DESIGN.md` (Presence states, sessions rail), `specs/GLOSSARY.md` (Thread, Turn, Place).

## Context

Phase 187 made the conversation reducer (`entities/conversation/model/reducer.ts`) the owner of every conversation frame, which makes it a deep module. Its state is then copied:

- **Copied into three maps.** `TurnFrameHandler` (`features/turn-stream/ui/TurnFrameHandler.tsx:39-53`) subscribes to the conversation store and copies each thread's state into three maps on the WS store: `thinkingThreads`, `typingTextThreads` and `attentionThreads` (`shared/api/ws-client.ts:10-12`).
- **Readers use the copies.** The sessions rail (`widgets/sessions-rail/ui/SessionsRail.tsx:32-33`) and Presence (`entities/presence/model/usePresence.ts:14-15`) read the copies, not the source.
- **A second writer.** `ConfirmationFrameHandler` (`features/respond-to-confirmation/ui/ConfirmationFrameHandler.tsx:17-19`) writes `thinking=false` and `attention=true` straight into the copy. `TurnFrameHandler` (`:94-97`) applies `paused` to the reducer for the same frame. The reducer's `attention` then flows back over the copy on the next sync (`:49`). This is the root of bug B10.
- **The disconnect path reads the copy.** It reads `thinkingThreads` to mark interrupted threads (`ws-client.ts:94-105`), and the watchdog consumes `interruptedThreads` (`features/turn-stream/model/watchdog.ts:62`).
- **"Is this turn running?" is computed in 11 places, with three meanings:**
  - *awaiting | thinking | speaking*:
    - `reducer.ts:97` (not exported)
    - `TurnFrameHandler.tsx:12`
    - `watchdog.ts:9`
    - `useSendTurn.ts:18`
    - `useRetryReply.ts:24`
    - `AskPage.tsx:67`
    - `TraceModule.tsx:39`
    - `AskOverlay.tsx:33`
    - `RetryControl.tsx:16`
  - *The same plus paused*: `TraceFrameHandler.tsx:6`.
  - *awaiting | thinking only*: `Canvas.tsx:85`.
- **The "held with no thread" rule is copied.** The rule "a held confirmation with no thread is skipped" appears in both `TurnFrameHandler.tsx:95` and `ConfirmationFrameHandler.tsx:12`.
- **Raw conversation frames outside turn-stream.** Two modules outside the turn-stream feature send them: `widgets/assemble/ui/RetryControl.tsx:31` sends `command cancel`, and `entities/conversation/api/useThreadHistory.ts:22` sends `ack`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A background thread asking for a confirmation is flagged in the rail (Priority: P1)

The user is on thread A. Thread B's turn parks a write and sends a confirmation request. The sessions rail shows B's attention mark and stops showing it as thinking. Opening B shows the card and clears the mark.

**Why this priority**: This is the visible failure (B10). A missed confirmation leaves a write paused until it times out.

**Independent Test**: A reducer-level test feeds `confirm_request` for a thread that is not open and reads the thread's flags through the exported selectors. A render test of the sessions rail shows the mark.

**Acceptance Scenarios**:

1. **Given** thread B is thinking in the background, **When** a `confirm_request` for B arrives, **Then** B reads paused and attention through the selectors, and the rail shows B's attention mark and no thinking mark.
2. **Given** B has the attention mark, **When** the user opens B, **Then** attention clears and the card shows.
3. **Given** the open thread A receives a `confirm_request`, **When** it is applied, **Then** A reads paused and does not get the attention mark.
4. **Given** a held confirmation with no thread, **When** it arrives, **Then** no thread's turn state changes, and the pending-confirmation store still keeps the card.

---

### User Story 2 — Every module agrees whether a turn is running (Priority: P1)

The Ask bar, Retry, the trace module, the overlay, the canvas, Presence and the delivery watchdog all ask the conversation module the same question, so none can disagree.

**Why this priority**: Today one place counts `paused` as running, another leaves out `speaking`, and the rest do neither. The send lock, Retry and the trace can contradict each other on the same thread.

**Independent Test**: A table test over every `TurnPhase` checks the exported selectors. A source search shows that no module outside `entities/conversation` compares turn phases to decide whether a turn is running.

**Acceptance Scenarios**:

1. **Given** each turn phase, **When** the selectors are read, **Then** they answer from one table: running, streaming, paused, failed or idle.
2. **Given** a turn is speaking, **When** the user looks at the Ask bar, Retry and the canvas working mark, **Then** each shows what the selectors say for speaking.
3. **Given** a turn is paused for a confirmation, **When** the trace frame handler starts a new turn, **Then** it still does not clear a pending trace. The behaviour is unchanged, now expressed through a named selector.

---

### User Story 3 — A dropped connection marks in-flight turns interrupted without a copy (Priority: P2)

When the socket drops, every thread whose turn was running is marked interrupted in the conversation state. The watchdog reloads those threads on reconnect.

**Why this priority**: Today this is the last reader of the WS-store copy.

**Independent Test**: Simulate a disconnect while one background thread and the open thread are running. Both read interrupted, and reconnecting reloads both.

**Acceptance Scenarios**:

1. **Given** two threads are running, **When** the socket closes (not displaced), **Then** both threads read interrupted and neither reads running.
2. **Given** an interrupted thread, **When** the socket reconnects, **Then** its history reloads once and its interrupted flag clears.
3. **Given** the window was displaced (close 4000), **When** it closes, **Then** turns are marked interrupted and no reconnect starts, as today.

---

### User Story 4 — Conversation frames leave the client through turn-stream only (Priority: P3)

Cancel, ack and send go through the turn-stream feature's interface. Widgets and entities do not build conversation frames.

**Why this priority**: It keeps the frame shapes in one module, but nothing visible depends on it.

**Independent Test**: A source search shows no `send({ type: "command" | "ack" | "message" … })` outside `features/turn-stream` and `shared/api/ws-client.ts`. The Retry busy-cancel and the history ack still work.

**Acceptance Scenarios**:

1. **Given** Retry reports busy, **When** the user taps Cancel, **Then** a cancel for that thread is sent through turn-stream.
2. **Given** a thread's history loads with unread assistant messages, **When** the load completes, **Then** one ack goes out through turn-stream.

### Edge Cases

- A `confirm_request` arrives for a thread the client has never opened. It creates the thread's state with paused and attention. It does not create messages.
- A `confirm_cancel` or a normal answer resumes the thread. Paused clears, and attention clears if the thread is open.
- A turn finishes in the background while the thread has attention. Attention stays until the thread is opened, as today.
- The socket drops while a thread is paused. A paused turn is not running, so it is not marked interrupted, and the pending card stays.
- Several frames for one thread arrive in one tick. The selectors read the final state, with no flicker from a sync step.
- Typing text exists only while the turn is running. The selector returns nothing for any other phase.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The conversation module MUST be the only store of per-thread turn state: running, typing text, paused, attention and interrupted. No other client store may hold a per-thread copy of these values.
- **FR-002**: The conversation module MUST export named selectors for whether a thread's turn is running, streaming (running and receiving tokens), paused for a confirmation, needs attention, its typing text, and whether it was interrupted. Callers MUST NOT compare turn phases themselves.
- **FR-003**: The running selector MUST answer from one phase table with one documented meaning. Any module that needs a different question (the trace's "a turn is in progress, paused included", or the canvas's "working before tokens") MUST get its own named selector from the same module.
- **FR-004**: A `confirm_request` for a thread MUST be applied as one conversation event. That event sets the thread paused, sets attention when the thread is not the open one, and ends the thinking display.
- **FR-005**: The rule that a held confirmation with no thread changes no thread's turn state MUST live in exactly one place.
- **FR-006**: The WS store MUST keep only connection state: connected, displaced, and the connection lifecycle. The `thinkingThreads`, `typingTextThreads`, `attentionThreads` and `interruptedThreads` maps and their setters MUST be removed (pre-v1 hard cut, constitution VIII).
- **FR-007**: A socket close MUST mark every thread whose turn is running as interrupted in the conversation state, through a connection-lifecycle signal the turn-stream feature subscribes to. Shared code MUST NOT import entities (FSD).
- **FR-008**: The sessions rail, Presence, the trace frame handler and the delivery watchdog MUST read thread state only through the conversation selectors, or through events the conversation module emits.
- **FR-009**: The subscription in `TurnFrameHandler` that copies conversation state into the WS store MUST be deleted.
- **FR-010**: Outbound conversation frames (message, ack, cancel command) MUST be built only inside the turn-stream feature, behind functions it exports. `RetryControl` and `useThreadHistory` MUST call those functions.
- **FR-011**: The frame registry (`features/turn-stream/model/frame-registry.ts`) and its coverage test MUST be updated so `confirm_request` names its conversation-state role next to the pending-confirmation store's role.
- **FR-012**: Presence states and wording, rail marks, the watchdog timings and the Retry behaviour MUST stay as `DESIGN.md` and phases 187 and 193 define them. This phase changes where state lives, not what the user sees, except for fixing B10.

### Key Entities

- **Thread turn state**: per thread, the turn's phase, typing text, attention and interrupted. Owned by the conversation module.
- **Turn selectors**: the named questions other modules may ask of a thread's turn state.
- **Connection lifecycle signal**: connected, closed (with or without displacement) and reconnected, published by the shared WS client with no per-thread data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero modules outside `entities/conversation` compare turn phases to decide whether a turn is running. Today there are 10, verified by a source search.
- **SC-002**: Zero per-thread maps remain in the WS store. Today there are four.
- **SC-003**: The background-confirmation scenario (US1, AS1–AS3) passes as a reducer test and a sessions-rail render test.
- **SC-004**: All existing reducer, `TurnFrameHandler`, watchdog, Presence, sessions-rail and frame-coverage tests pass. Their assertions may move to selectors, but no scenario is dropped.
- **SC-005**: The Ask, World and Doing places render and send a turn in the agent's own portal, checked with the `ze-web-verify` skill, with a screenshot of the rail attention mark on a background thread.

## Assumptions

- Phase 198 has landed a minimal B10 fix plus a regression test. This phase keeps that test and deletes the code path it patched.
- The pending-confirmation store (`features/respond-to-confirmation/model/pending-store`) keeps the cards. Only its writes into the WS store move.
- No backend or frame-shape change: the WS protocol is untouched.
- The `entities/conversation` slice may grow a `model/selectors.ts`. FSD layering stays: features and widgets import from the entity index.

## Out of Scope

- Cache invalidation on frames (phase 206).
- The trace store's own data (phases 208 and 187b). Only its "new turn" trigger changes here.
- Renaming sessions to threads in the rail and REST (phase 207, `thread-not-session.md`).
