# Feature Specification: WS Conformance Harness

**Feature Branch**: `219-ws-conformance-harness`

**Created**: 2026-10-22

**Status**: Draft

**Input**: User description (approved 2026-10-22, "go ahead with all of it"): architecture review 2026-10-22, candidate C21. The phase has three parts:

- A test harness that opens the real `/ws` endpoint, with a scripted fake turn module, and validates every frame the server emits against the declared frame union.
- Optional frame validation in `send_frame` for dev and eval runs.
- A generated ze-client WS export list, replacing the hand-kept one and adding the frames it is missing.

**Governed by**: phase 72 (API client codegen; WS types from Pydantic via `json-schema-to-typescript`), phase 117 (backend keeps the socket on unserializable frames; terminal `error` frame), phase 187 (frame registry: one state owner per frame on the web side), `specs/arch/pre-v1-hard-cuts.md`.

**Depends on**: 207 (conversation turn module). The harness drives `/ws` against 207's turn module through a scripted fake behind its port, and checks 207's single error-frame shape.

**Doctrine functions served**: governance (the protocol the web app relies on is checked where frames are sent, so drift is caught before the client sees it).

**Owning packages** (for planning): ze-api (tests, `ConnectionManager.send_frame`, `ws/endpoint.py`), ze-client (`src/ws.ts`, `src/index.ts`, `scripts/codegen.ts`), ze-web (consumers that use `Extract<WsInboundFrame, …>` because named exports are missing). No migration.

## Context

- **Naming.** In `apps/ze-api/ze_api/api/ws/schemas.py` the names are from the client's point of view:
  - `WsInboundFrame` (`:216`) is the union of frames the **server sends**. It has 14 members: message, edit, confirm_request, confirm_cancel, typing, token, error, message_superseded, message_rollback, refresh, pong, trace_update, notification, ui_action_result.
  - `WsOutboundFrame` (`:352`) is the union of frames the **client sends**.

  The review's "validate against `WsOutboundFrame`" had the direction backwards. Server frames validate against `WsInboundFrame`.
- **How the server sends frames today:**
  - 93 `send_frame(` call sites build frames as dicts, 52 of them `"type": "error"`.
  - Six `ws.send_json(` calls in `endpoint.py` bypass `ConnectionManager` and its lock: `pong` at `:115`, and error frames at `:141, :176, :219, :245`.
  - `ConnectionManager.send_frame` (`connection.py:157`) validates nothing.
- **Error frames drift.** `confirmation.py:152` sends busy without `code`; `endpoint.py:147,225,251` send `code: "busy"`.
- **Tests.**
  - Unions are checked only in unit round-trips (`tests/api/test_ws_schemas.py`, `test_schemas_rollback.py`).
  - `tests/api/test_ws_conformance.py` (496 lines) exists but drives handlers with a mocked socket, never the endpoint. Its docstring still names `apps/ze-web/src/ws/protocol.ts`, which no longer exists.
  - No test calls `websocket_connect`. So frame dispatch, auth, the busy flags, gate tracking and the confirm path in `endpoint.py:104-271` are untested through the interface.
- **ze-client exports.** `packages/ze-client/src/ws.ts` re-exports a hand-kept list from `src/generated/ws.ts`, and `src/index.ts` repeats it. The list leaves out frames the generator already produces:
  - `WsMessageSupersededFrame`, `WsMessageRollbackFrame`, `WsNotificationFrame`, `WsUiActionResultFrame`;
  - `WsActionFrame`, `WsUiActionFrame`, `WsRetryFrame`;
  - `WsConfirmItem`, `WsUiToolAction`.

  Web callers work around the gaps with `Extract<WsInboundFrame, …>`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every frame the server sends matches the protocol (Priority: P1)

A developer changes a handler and sends a frame the protocol does not declare, or leaves out a field. The test suite fails and names the frame, before the web app ever receives it.

**Why this priority**: the web app's single state owner per frame (phase 187) is only as good as the frames it receives. Drift is invisible today.

**Independent Test**: run the harness. It opens `/ws`, runs a scripted conversation (message → token → reply; a turn that pauses for confirmation, then approve; Retry; busy; an unknown confirmation id; a ping) and validates every received frame against the server-frame union.

**Acceptance Scenarios**:

1. **Given** the scripted conversation, **When** it runs, **Then** every received frame validates, and the run fails on the first one that does not, naming its type and field.
2. **Given** a busy thread, **When** a second message arrives, **Then** the error frame carries `code: "busy"` on every path.
3. **Given** a missing or wrong API key, **When** the socket opens, **Then** it is closed with the documented code.

---

### User Story 2 - Dev and eval runs catch bad frames live (Priority: P2)

While running `make dev` or `make dev-eval`, a frame that fails validation is logged with its type and the first failing field. With strict mode on, it is refused instead of sent. Production behaviour is unchanged.

**Why this priority**: tests cover scripted paths; live validation catches the rest during dogfooding and evals at little cost.

**Independent Test**: with validation on, send a malformed frame through `send_frame` and assert one warning (or refusal in strict mode). With validation off, assert it is sent unchanged.

**Acceptance Scenarios**:

1. **Given** validation is on, **When** a valid frame is sent, **Then** it goes out unchanged.
2. **Given** validation is on and the frame is invalid, **Then** a structured warning is logged. With strict mode, the frame is not sent and an `error` frame is sent instead.

---

### User Story 3 - The client package exports every frame by name (Priority: P3)

A web developer imports any server or client frame type by name from `@myguyze/ze-client`. When the backend adds a frame, codegen exports it with no hand edit.

**Why this priority**: it removes a hand-kept list that has already drifted, but changes no behaviour.

**Independent Test**: run codegen, then check that every member of both unions, and every named model they reference, is importable by name from the package root.

**Acceptance Scenarios**:

1. **Given** codegen has run, **When** the export surface is compared with the generated module, **Then** they are the same set.
2. **Given** web code that uses `Extract<WsInboundFrame, {type: …}>` for a frame that now has a name, **When** it is updated, **Then** it imports the named type.

### Edge Cases

- A frame is unserializable (phase 117). The harness asserts the socket stays open and a terminal `error` frame follows.
- A displaced connection (close code 4000). The harness asserts the old socket closes with 4000 and the new one replays unread messages.
- Replayed pending confirmations on connect are validated like live frames.
- A plugin `refresh` frame with `module:<id>` validates against the refresh frame.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The test suite MUST include a harness that connects to the real `/ws` endpoint in process and replaces the turn module with a scripted fake through its port (phase 207). It MUST NOT need a database, a model or the network.
- **FR-002**: The harness MUST validate every frame the server sends against the server-frame union, including frames replayed on connect.
- **FR-003**: The harness MUST cover at least:
  - auth reject;
  - message, token and reply;
  - a confirmation pause and approve;
  - deny;
  - timeout;
  - Retry;
  - busy;
  - unknown confirmation id;
  - ping/pong;
  - displacement (4000);
  - unserializable-frame recovery.
- **FR-004**: Every server frame MUST be sent through `ConnectionManager`. The direct `ws.send_json` calls in the endpoint MUST be removed.
- **FR-005**: `send_frame` MUST support opt-in validation against the server-frame union, controlled by settings: off, warn, or strict. It is off by default in production and on (warn) for `make dev` and `make dev-eval`.
- **FR-006**: The ze-client package MUST export every member of both frame unions, and every named model they reference, from a list generated by codegen. The hand-kept lists in `src/ws.ts` and `src/index.ts` MUST be removed.
- **FR-007**: The stale mocked-socket conformance tests MUST be either moved onto the harness or deleted where the harness covers them. No test may cite a client file that does not exist.

### Key Entities

- **Server frame**: a frame Ze sends to the client (`WsInboundFrame` in schemas).
- **Client frame**: a frame the client sends to Ze (`WsOutboundFrame`).
- **Scripted turn**: a fake turn-module behaviour for a harness run, emitting a fixed sequence of turn events.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The harness covers 100% of the 14 server frame types at least once.
- **SC-002**: No production code in the WS endpoint sends JSON directly. Searching for `ws.send_json(` outside `ConnectionManager` finds nothing.
- **SC-003**: A deliberately malformed frame added to any handler fails the suite in under one test run.
- **SC-004**: The ze-client export surface equals the generated surface, checked by a test or by the codegen check.

## Assumptions

- Phase 207 provides a turn-module port that a scripted fake can satisfy. If 207 slips, the harness can fake the container's turn entry points, but that version is temporary within this phase.
- FastAPI's in-process websocket test client is enough; no real server is started.
- Strict mode is for local and eval use only; it is never turned on by default.
