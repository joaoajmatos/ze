# Feature Specification: Conversation Turn Module

**Feature Branch**: `207-conversation-turn-module`

**Created**: 2026-10-22

**Status**: Draft

**Input**: User description (approved 2026-10-22, "go ahead with all of it"): architecture review 2026-10-22, candidate C1 together with the ze-api findings #3 (Retry as one module) and #4 (one confirmation gate registry). One turn module owns the turn lifecycle: user-message persistence, thread bookkeeping, confirmations across graph, held and UI gates keyed by `request_id`, Retry and rollback state, and delivery. It emits turn events to a port, and WS, eval and workspace follow-up are its adapters. `ThreadTurnLock` moves out of ze-workspace. The per-socket `pending_configs` is deleted. Error frames become consistent. The phase also delivers the thread-not-session hard cut, and the rule that approving a parked write clears a held write for the same tool and arguments.

**Governed by**: `specs/arch/thread-not-session.md`, `specs/arch/pre-v1-hard-cuts.md` (constitution Principle VIII), `specs/arch/langgraph-orchestration.md` (LangGraph stays the engine; this phase moves only what the shell does around `invoke_raw_turn`/`resume_turn`), phase 180 (Retry rollback), phase 181 (irreversible write confirmation and held writes), phase 191a (UI action gates), `specs/GLOSSARY.md` (Thread, Session, Turn, Confirmation, Parked write, Held write, Approval, Retry, Rollback).

**Depends on**: 201 (typed turn services: the turn module reads services from it instead of `container._build_config`). 198 ships the interim fix for B9, so this phase replaces that fix rather than racing it.

**Doctrine functions served**: governance (one place decides how every confirmation is asked, answered, timed out and superseded), action (every turn path, including evals and follow-ups, persists and delivers the same way).

**Owning packages** (for planning): ze-api (`ze_api/api/ws/*`, `ze_api/api/eval/router.py`, `ze_api/wiring/container.py`, the sessions REST router), ze-core (`ze_core/conversation/` keeps `invoke_raw_turn`, retry eligibility and the sessions store, which becomes the threads store), ze-workspace (loses `turn_lock.py`; its follow-through calls a turn port), ze-automation (held-write store lookup by tool and arguments), ze-client (regenerated SDK and WS types), ze-web (threads rail and query keys). Migration: rename `sessions` → `threads` (ze-core `zc` chain).

## Context

A turn is started or resumed from seven places, and each rebuilds the work before and after the turn by hand. The code shows how they disagree:

- **WS message** (`apps/ze-api/ze_api/api/ws/turns.py:62` `handle_message`, through about line 216). It saves the user message with its screen context, upserts the session, builds the token sink, progress reporter and screen config, supersedes open confirmations, persists a new confirmation, sets the title and delivers. The token sink and progress reporter are built again at `turns.py:563-574` for Retry.
- **Eval** (`apps/ze-api/ze_api/api/eval/router.py:39` `eval_chat`, calling `container.invoke_raw_turn` at line 69). It does none of this, so evals never exercise the product's turn path. For example, Retry replays screen context from the stored user message, but an eval turn stores no user message.
- **Workspace follow-up** (`apps/ze-api/ze_api/wiring/container.py:138-168`, `_ContainerTurnStarter`). It returns early on `outcome.interrupted` (line 161). A follow-up turn that parks a write therefore sends no `confirm_request`, writes no `pending_confirmations` row and starts no timeout, so the graph stays paused with nothing on screen. This is bug B9 in the review. Phase 198 fixes it as a stopgap.
- **Confirm** (`apps/ze-api/ze_api/api/ws/endpoint.py:173-206`). One `confirm` frame is resolved by trying gate kinds in order:
  - UI gate (`handle_ui_confirm`, in process, `ui_gates.py`);
  - held write (`handle_held_confirm`, called inside `confirmation.handle_confirm` at `confirmation.py:119`);
  - graph confirmation.

  The `kind` that `confirm_request` already carries is not used to dispatch. A fourth, per-socket map, `pending_configs` (`endpoint.py:27-43`, `_track_gate`/`_untrack_gate`), is rebuilt from the database when it is missing.
- **Retry** is about 600 lines across modules:
  - `turns.py:297-644`: `_retry_error`, `_prepare_retry`, `handle_retry`, `_retry_locked`;
  - `rollback_state.py` (178 lines): `move_rollback`, `deliver_retry_reply`;
  - `confirmation.py:30-101` and `:380`: `_without_retry_identity`, `_retry_without_reply`, `_retry_identity`.

  These wrap one pure `retry_eligibility`, whose inputs are gathered in the REST views module `api/v0/messages/views.py`.
- **Error frames drift.** `confirmation.py:152` sends `{"type": "error", "detail": "busy"}` with no `code`, while `endpoint.py:147,225,251` send `code: "busy"`. Eleven `ws.send_json` calls bypass `ConnectionManager.send_frame` (93 `send_frame` calls).
- **The lock lives in the wrong package.** `ThreadTurnLock` (`core/ops/ze-workspace/ze_workspace/turn_lock.py:8`) is a conversation concept. `container.py:47,478` and `lifespan.py:32` import it from ze-workspace.
- **"Session" means three things** (`specs/arch/thread-not-session.md`):
  - the `sessions` table, whose id is the thread id (`zc018_sessions.py:21`);
  - the `SessionStore` (`ze_core/conversation/sessions/store.py:206`);
  - `/api/v0/sessions` (`api/v0/sessions/router.py`) and the web `widgets/sessions-rail` and `entities/session`.

  "Session" is also used for an inactivity burst.

Blast radius (`graphify affected --depth 2`):

| Symbol | Production callers | Tests |
|---|---|---|
| `handle_confirm` | `endpoint.py`, `main.py` | about 12 tests across `test_ws_confirmation_retry.py`, `test_ws_confirmation_supersede.py`, `test_ws_retry_rollback.py` |
| `send_confirmation_request` | `endpoint.py:_run_message_task`, `turns.handle_retry`, `component_submit.handle_component_submit` | `test_ws.py`, `test_ws_conformance.py`, `test_ws_screen_context.py`, `test_ws_voice_turn.py`, `test_ws_write_confirmation.py` |
| `handle_retry` | `endpoint.websocket_endpoint` | `test_retry_rollback_e2e.py` (8 tests), `test_ws_retry_rollback.py` |
| `ThreadTurnLock` | `lifespan.py`, `cli/seed.py`, `wiring/container.py` | four container tests |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A follow-up turn that needs my yes asks for it (Priority: P1)

A detached workspace run finishes while the user is away. Its follow-up turn wants to send an email, which asks first. The user sees a confirmation in the Ask thread, or gets a push if they are offline, exactly as for a turn they typed.

**Why this priority**: today the turn silently stays paused (B9). It is the only lost-confirmation path the review found, and it breaks phase 181's guarantee.

**Independent Test**: start a follow-up turn through the follow-up adapter with an agent stub that parks one asks-first write. Then assert three things: one `confirm_request` event, one stored pending confirmation with a timeout, and a resume on approve.

**Acceptance Scenarios**:

1. **Given** a follow-up turn whose agent parks a write, **When** the turn pauses, **Then** a confirmation is stored, sent to the connected client (or pushed when no client is connected) and timed out like any other.
2. **Given** that confirmation, **When** the user approves it, **Then** exactly the approved call runs and the reply is delivered on the same thread.

---

### User Story 2 - Evals run the product's turn path (Priority: P1)

An eval scenario sends a message. The turn stores the user message (with any screen context), updates the thread, persists and supersedes confirmations, and produces the same reply and trace the web app would get.

**Why this priority**: evals are the acceptance gate for most phases. While they skip the shell's before and after steps, regressions in persistence, Retry replay and confirmation handling cannot show up in evals.

**Independent Test**: run one eval turn through the eval adapter and assert that the stored user message, the thread row and the trace match a WS turn with the same input.

**Acceptance Scenarios**:

1. **Given** an eval turn with screen context, **When** it is retried through the eval confirm surface, **Then** the retry replays the stored screen context.
2. **Given** an eval turn that parks a write, **When** the scenario sends `confirm:`, **Then** the turn module resolves it through the same gate registry as WS.

---

### User Story 3 - One answer resolves exactly one gate (Priority: P2)

The user answers a confirmation. Whatever produced it (a paused graph turn, a held write from an unattended run, a UI action gate), Ze looks up the gate by its id, applies the answer once, and reports one outcome frame.

**Why this priority**: today one answer is matched by trial in a fixed order, a second in-memory map can disagree with the database, and busy errors differ by path.

**Independent Test**: register one gate of each kind, send each a confirm frame, and assert that each is resolved by its own adapter with no fall-through and the same error shape for unknown, stale and busy cases.

**Acceptance Scenarios**:

1. **Given** a held write and a graph confirmation open at the same time, **When** the user answers the held write's id, **Then** only the held write is decided.
2. **Given** a stale id, **When** it is answered, **Then** the user gets the same error frame shape on every path, with `code` set.
3. **Given** a socket reconnect, **When** a confirmation is open, **Then** it is replayed from the store, with no per-socket state needed.

---

### User Story 4 - Approving in chat clears the matching held write (Priority: P2)

A nightly workflow held "send the weekly email to Ana". In the morning the user asks for the same thing in chat and approves the parked write. The held write for the same tool and arguments is marked approved (consumed), so Needs you no longer shows it and the workflow does not send a second email.

**Why this priority**: the glossary defines one pending decision per action. Without this rule, the user approves the same action twice.

**Independent Test**: create a held write and a parked write with the same tool and arguments. Approve the parked write, and assert that the held write is no longer open and is never resumed.

**Acceptance Scenarios**:

1. **Given** an open held write and a parked write with the same tool and the same arguments, **When** the parked write is approved and runs, **Then** the held write is closed as already done and its run is told so.
2. **Given** arguments that differ, **When** the parked write is approved, **Then** the held write stays open.
3. **Given** the parked write is denied, **Then** the held write is unchanged.

---

### User Story 5 - Retry is one module (Priority: P2)

The user presses Retry on the latest reply. Ze checks eligibility, takes the thread lock, checks again, matches the confirmed plan, rolls back, regenerates and records each rollback state, through one module that reports through the same turn events as a normal turn.

**Why this priority**: Retry's state machine is spread across five files and two concurrency guards (the per-connection busy flag and `ThreadTurnLock`). The interface is the test surface, so Retry should be testable through its interface, not through mocked internal handlers.

**Independent Test**: drive Retry through the turn module with a fake delivery port and assert each documented state from phase 180 (`partial`, `rolled_back_awaiting_confirmation`, `rolled_back_retry_failed`, `superseded`, `plan_changed`, `undo_not_confirmed`).

**Acceptance Scenarios**:

1. **Given** the existing phase 180 end-to-end scenarios (`test_retry_rollback_e2e.py`), **When** they run against the turn module through a test adapter, **Then** they pass unchanged in outcome.
2. **Given** a Retry while a turn on the same thread is running, **Then** one guard refuses it with the busy error.

---

### User Story 6 - It is called a thread everywhere (Priority: P3)

The Ask rail lists threads. REST lists `/api/v0/threads`. SDK methods, WS fields and stored rows say thread. "Session" only means a burst of activity on a thread (resume recap, compaction, spend ceiling).

**Why this priority**: it is a naming hard cut with no behaviour change, so it ranks below the fixes. It is cheapest while this phase already rewrites thread bookkeeping.

**Independent Test**: the sessions routes, types and table no longer exist; the threads equivalents list and search the same data; the web rail renders from the threads query.

**Acceptance Scenarios**:

1. **Given** the migration has run, **When** the threads list is requested, **Then** it returns what the sessions list returned before, in the same order.
2. **Given** the codebase, **When** it is searched for `session_id` used to mean a thread id, **Then** there are no results outside onboarding and the burst meaning.

### Edge Cases

- A confirmation's gate kind is unknown, for example after a restart that dropped in-process UI gates. The answer is refused with a plain line and `code`, and nothing else runs.
- A held write expires at the moment the chat approval clears it. Expiry and clearing are one state change, and whichever lands first wins.
- A follow-up turn arrives while the user is typing on the same thread. The thread lock serializes them. The follow-up waits; it does not drop.
- An eval turn passes no thread id. It gets a fresh thread and that thread is recorded, just as a new WS thread is.
- The client reconnects mid-Retry. The rollback state is read from the stored message record, never from socket memory.
- The `sessions` → `threads` migration runs on a database with rows. Every row keeps its id, title and last-active time.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST have one turn module that starts a turn, resumes a paused turn and runs a Retry. For every caller it persists the user message (with screen context and voice input), updates the thread, supersedes open confirmations, stores any new confirmation with its timeout, and delivers the outcome.
- **FR-002**: The turn module MUST report outcomes as turn events to a delivery port: reply, token, typing, confirmation opened, confirmation cancelled, rollback, error. It MUST NOT build transport frames itself.
- **FR-003**: WS, eval and workspace follow-up MUST be adapters of that port. The WS adapter builds frames. The eval adapter collects events into the eval response. The follow-up adapter delivers to the interface (WS frame or push).
- **FR-004**: Every path that can pause a turn (message, follow-up, component submit, UI action, Retry, eval) MUST produce a stored, timed confirmation through the turn module. This replaces the phase 198 stopgap for B9.
- **FR-005**: The system MUST resolve a confirmation answer by looking up its `request_id` in one gate registry that records the gate's kind (graph, held, UI). It MUST NOT try kinds in order.
- **FR-006**: The per-socket `pending_configs` map and `_track_gate`/`_untrack_gate` MUST be deleted. Resume configuration comes from the stored confirmation.
- **FR-007**: Every error the turn path emits MUST use one frame shape with `code` set for machine-readable cases (busy, unknown or stale confirmation, retry errors). All frames MUST go through `ConnectionManager.send_frame`.
- **FR-008**: Retry eligibility, the locked recheck, plan-confirmation matching, rollback, regeneration and rollback state moves MUST live in one Retry module behind the turn module's interface. `ze_api/api/ws/` keeps only frame translation.
- **FR-009**: There MUST be one concurrency guard per thread. `ThreadTurnLock` MUST move from ze-workspace to the conversation module that owns turns, and the per-connection busy flag MUST either be derived from that guard or be removed.
- **FR-010**: When a parked write is approved and runs, the system MUST close every open held write whose tool and arguments are identical, recording it as already done. A denial MUST leave held writes unchanged.
- **FR-011**: The system MUST rename the conversation concept to **thread** in the table, store, REST routes, SDK methods, WS fields and web rail, with no aliases (`specs/arch/thread-not-session.md`). Onboarding sessions keep their name. The inactivity-burst meaning keeps the word session.
- **FR-012**: Turn persistence before and after the turn MUST NOT be duplicated anywhere outside the turn module. The token sink, progress reporter and thread upsert MUST each be built in one place.

### Key Entities

- **Turn**: one user input (or follow-up prompt, or Retry) and Ze's handling of it, ending in one reply or one pending confirmation.
- **Turn event**: one observable outcome of a turn, delivered to the port.
- **Gate**: one open request for the user's answer, with an id, a kind (graph, held, UI), a thread and an expiry. (This is not the goal gate. Planning picks a name that does not clash with the glossary's **Gate**, for example "pending confirmation".)
- **Thread**: one conversation; replaces the session-as-conversation record.
- **Held write / Parked write**: as in the glossary. They are matched by tool plus canonical arguments.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A follow-up turn that parks a write produces a visible confirmation 100% of the time in the end-to-end test. Today it is 0%.
- **SC-002**: Exactly one module in the shell starts or resumes turns. Searching for `invoke_raw_turn` or `resume_turn` outside it and its adapters finds nothing.
- **SC-003**: The ws/ package shrinks to frame translation and dispatch. Retry and confirmation lifecycle code no longer lives under `ze_api/api/ws/`.
- **SC-004**: All phase 180 and 181 end-to-end scenarios pass through the new interface, and the eval suite's confirmation scenarios pass through the eval adapter.
- **SC-005**: Every error frame the server can emit validates against the declared error frame union with `code` set where the union defines one.
- **SC-006**: No user-visible or API surface uses "session" to mean a conversation.

## Assumptions

- Phase 201 lands first and gives the turn module typed services. If it slips, the turn module can read the current services, but this phase does not add new `configurable` keys.
- In-process UI gates (191a) are allowed to be lost on restart. The registry records their kind so a late answer is refused cleanly rather than misrouted.
- "Same tool and arguments" uses the canonical argument form phase 181 already uses for duplicate detection (`(tool, args)` identity).
- ze-web changes are limited to the rename and to consuming any new error `code` values. The turn-state work in phase 205 is separate.
- Dev data is disposable. The rename migration moves rows but does not keep old names (Principle VIII).
