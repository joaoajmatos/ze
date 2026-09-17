# Feature Specification: Concurrent Thread Identity

**Feature Branch**: `159-concurrent-thread-identity`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "Specs for Multi-conversation (99): One WebSocket still displaces the previous. Conductor + promote assume the thread."

**Governed by**: [`specs/arch/companion-conductor-roadmap.md`](../../arch/companion-conductor-roadmap.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md), [`specs/arch/single-user-model.md`](../../arch/single-user-model.md), Phase 99 [`099-multi-conversation`](../099-multi-conversation/spec.md), confirmations [`113-hardening-sweep`](../113-hardening-sweep/spec.md), conductor 151–158.

**Depends on**: Phase 99 transport (already in tree: one multiplexed socket, `ThreadSlot` busy per `thread_id`, client `thinkingThreads` / ChatNav). Phases 113 (`request_id` confirmations), 151–158 (conductor/promote).

**Does not start**: Multi-user accounts; second live WebSocket per tab as a product; restoring MiniLM; swarm.

---

## Overview

Phase 99’s **transport is already live**: one browser session keeps one WebSocket; conversations multiplex with `thread_id`; a thread can be busy while another accepts a message; confirmations replay by `request_id`. A **new socket still closes the old one with code 4000** — that is one live *client*, not one live *conversation*.

What still assumes “the” thread is the **conductor-era UI and control plane**: the trace/mind panel applies every `trace_update` to a single store; cancel uses the first pending config; promote/timeout/ntfy can talk as if one job is on screen. Two chats can run; the user can still see the wrong plan, cancel the wrong conductor, or miss a promote offer on the thread that actually stalled.

This phase finishes 99 for 151–158. It does **not** rebuild `ConnectionManager`. Close 4000 stays: one live UI for the single user.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Two conversations can run without stealing the trace (Priority: P1)

The user has chat A (a conductor: research then mail) and chat B (calendar). Both can be in flight. The trace panel for the open chat shows **that** chat’s plan and specialists. Switching chats shows the other chat’s trace, not a mash of both.

**Why this priority**: Conductor observability (154) is a lie if the panel is global.

**Independent Test**: Two `trace_update` frames with different `thread_id`s; the store/UI bound to thread A ignores B’s frames (or keeps them in a per-thread map). Opening B shows B.

**Acceptance Scenarios**:

1. **Given** thread A is active and a `trace_update` arrives for thread B, **When** the trace panel renders, **Then** it does not replace A’s conductor ledger with B’s.
2. **Given** the user selects thread B, **When** the panel renders, **Then** it shows B’s latest trace (or empty), not A’s leftover.
3. **Given** 99’s per-thread thinking flags, **When** A is busy and B is idle, **Then** ChatNav still spins only on A.

---

### User Story 2 - Cancel and promote belong to a thread (Priority: P1)

The user cancels or is offered a promote/timeout on the conversation that actually needs it. A `/cancel` (or equivalent) on thread A does not abort thread B’s conductor. A 157 promote offer after timeout names that thread.

**Why this priority**: 157 and 156 are thread-local jobs; a global first-pending pointer reintroduces “the” thread.

**Independent Test**: Two pending confirmations on two threads. Cancel/command with thread A’s identity only clears A. Timeout copy/ntfy includes A’s `thread_id`.

**Acceptance Scenarios**:

1. **Given** pending conductor confirmations on threads A and B, **When** the user cancels on A, **Then** B’s pending config and busy slot remain.
2. **Given** a confirmation timeout on thread A, **When** the user is notified or offered promote (157), **Then** the frame/ntfy is tagged with A’s `thread_id` (not an unlabeled global).
3. **Given** thread A is busy with a conductor, **When** the user sends on thread B, **Then** B is not rejected as globally busy (99 `try_set_busy` per thread — must remain).

---

### User Story 3 - One live client, many conversations (Priority: P2)

Opening a second tab still displaces the first socket (4000). Switching conversations in the **same** tab does not reconnect. The user is one person with one live UI and many threads.

**Why this priority**: The user named 4000. It is the single-client rule, not a conversation bug. Pin it so 159 does not “fix” it by allowing two sockets.

**Independent Test**: Existing `test_ws` 4000 still passes. `selectSession` does not call `reconnect()`.

**Acceptance Scenarios**:

1. **Given** a connected client, **When** a second WebSocket authenticates, **Then** the first is closed with 4000 (unchanged).
2. **Given** the user picks another session in ChatNav, **When** that happens, **Then** the socket stays up (no reconnect).
3. **Given** this phase, **When** documenting 99, **Then** 99 is marked transport-shipped; remainder is this spec (no second multiplexer).

---

## Edge Cases

- `trace_update` without `thread_id`: ignore or attach to the sending turn’s thread only — do not apply globally. **Assumption:** frames from the server already carry `thread_id` after 99; missing id is a bug, drop for the panel.
- Abort tokens already keyed by `thread_id` in `Container` — do not rekey to a singleton; do not clobber B when A starts.
- Speech-act one-shot on companion in thread B while A’s conductor is paused on confirmation: both legal.
- ntfy when the socket is up but that thread is not the visible chat: still in-session routing (99); do not push as if disconnected.
- Command frames with no `thread_id`: MUST NOT default to “first pending”; require `thread_id` or no-op with error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Trace / mind panel state MUST be per `thread_id`. A `trace_update` MUST NOT be applied to a thread it does not name.
- **FR-002**: Cancel/abort and pending graph configs MUST be selected by the user’s thread (and `request_id` for confirmations). The server MUST NOT abort “the first pending config” when more than one thread has work.
- **FR-003**: 157 promote / confirmation-timeout user-visible notices MUST carry the unfinished conductor’s `thread_id`.
- **FR-004**: Per-thread busy (99) MUST remain. A conductor on A MUST NOT mark the whole client busy.
- **FR-005**: Close code 4000 (one live WebSocket) MUST remain. Session switch MUST NOT reconnect. This phase MUST NOT add a second concurrent socket per user.
- **FR-006**: This phase MUST NOT rebuild `ConnectionManager` multiplexing, MUST NOT change 151–158 conductor rewrite/gates, MUST NOT restore `plan_sequential`.

### Key Entities

- **Live client**: The single authenticated WebSocket; displaced by 4000.
- **Conversation thread**: LangGraph `thread_id` / chat session; many per live client.
- **Per-thread trace**: The conductor/routing trace shown for the open conversation only.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of tested dual-thread `trace_update` fixtures keep traces isolated by thread.
- **SC-002**: 100% of tested dual-pending cancel fixtures abort only the named thread.
- **SC-003**: 100% of tested session-switch cases keep the same socket (0 reconnect).
- **SC-004**: Existing 4000 displace test still passes.
- **SC-005**: Phase 99 index row records transport shipped; this directory owns the remainder.

---

## Assumptions

- One live UI is correct for a single-user assistant (second phone/tab is a new client, not a second conversation channel).
- 99 ChatNav spinner/attention already work; 159 does not re-spec them unless a test shows they are global again.
- `pending_configs` keyed by `request_id` (113) stays; 159 fixes *selection* (cancel/command), not the key.

## Out of Scope

- Multi-user / multi-account.
- Split-view two chats on one screen (layout).
- Embedding model / routing thresholds (160).
- Procedures, swarm, sequential graph execute.

## Verbatim Constraints

- `thread_id`
- `request_id`
- `4000`
- `trace_update`
- `try_set_busy`
- `ConnectionManager`
- Principle VIII
