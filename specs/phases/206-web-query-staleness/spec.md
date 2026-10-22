# Feature Specification: Web Query Staleness — One Table, One Query Adapter

**Feature Branch**: `206-web-query-staleness`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: none

**Can run in parallel with**: 205. The file sets are disjoint, with one shared file: `features/retry-reply/model/useRetryReply.ts`. Phase 205 changes its running check at line 24; this phase changes its invalidation keys at lines 34-35. Let one lane own the file, or land this edit after 205.

**Input**: Architecture review 2026-10-22, candidate C19 ("A staleness table and one sdkQuery adapter"). Report: `architecture-review-2026-10-22.html`. Floor brief: `floor-briefs-2026-10-22.md`, Wave 1.

**Governed by**:
- Phases 186 and 193: client queries throw on error, so a failed read never reads as "nothing tracked".
- Phase 191b: `module:<id>` refresh frames.
- AGENTS.md ze-web FSD rules.

## Context

The rule "when a record of kind X changes, these queries are stale" is written in four places, and they disagree:

1. **`CORE_REFRESH_SCREEN_MAP`** (`shared/lib/query-keys.ts:62-66`) serves `refresh` frames.
2. **`WORLD_KEYS`** (`features/invalidate-on-ws-refresh/ui/RefreshHandler.tsx:7-15`) re-reads seven World queries on every assistant `message`, on every Place.
3. **`TARGET_KEYS`** (`RefreshHandler.tsx:18-25`) serves `notification` frames.
4. **Each mutation's `onSuccess`.** 23 files call `invalidateQueries`.

They disagree for the same record. A loop transition invalidates loops, the priority snapshot and the loop detail (`entities/loop/api/useLoopTransitionMutation.ts:27-31`). An `open_loop` notification invalidates loops only (`RefreshHandler.tsx:19`).

Thirteen sites bypass `queryKeys` with raw string keys:
- `useRetryReply.ts:34-35`
- `RefreshHandler.tsx:45`
- `useMarkAllReadMutation.ts:15`
- `useMarkReadMutation.ts:14`
- `useUpdateQuietHoursMutation.ts:20-21`
- `useDecideHeldWriteMutation.ts:25`
- `useHypothesisFeedbackMutation.ts:13-14`
- `useReviewFactMutation.ts:17`
- The query keys of `useMemoryActivityQuery.ts:7` and `useMemoryTimelineBoundsQuery.ts:7`

The `notification` frame's list item is built by hand inside a feature (`RefreshHandler.tsx:44-79`). Its shape belongs to `entities/notification`.

The entity hooks are pass-throughs:
- There are 67 hook files under `entities/*/api`, and 39 of them are 20 lines or fewer.
- `if (error) throw error` appears 53 times.
- `entities/query-errors.test.tsx` exists only to check that each hook remembers that line.
- One hook still swallows errors against the phase 186 and 193 rule. `features/trace-state/model/useSessionTraces.ts:24` returns `[]` on an error.

Procedures are one concept split across five hook files and two near-identically named feature slices: `features/procedure-review` (`ProcedureControls`) and `features/review-procedure` (`ReviewProcedureCandidate`). Both have exactly one consumer, `widgets/procedures/ui/Procedures.tsx:3-4`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Every change of a record refreshes the same views (Priority: P1)

Whether a loop changes because the user confirmed it, a notification about it arrived, or a refresh frame named it, every view that shows that loop re-reads.

**Why this priority**: The copies disagree today, so a loop notification leaves the priority snapshot and the loop detail stale. The user sees an out-of-date World.

**Independent Test**: A pure table test asserts which queries each record kind makes stale. A test feeds a `notification` for an `open_loop` and checks the same queries that a loop transition invalidates are invalidated.

**Acceptance Scenarios**:

1. **Given** the loop detail and the World field are open, **When** a notification about that loop arrives, **Then** the loops list, the priority snapshot and that loop's detail re-read.
2. **Given** the user confirms a loop on World, **When** the transition succeeds, **Then** exactly the same set re-reads.
3. **Given** a `refresh` frame for `module:<id>`, **When** it arrives, **Then** that module's tree re-reads, as in phase 191b.
4. **Given** a `refresh` frame for a screen the table does not know, **When** it arrives, **Then** nothing is invalidated and nothing fails.

---

### User Story 2 — A failed read is an error everywhere, by construction (Priority: P1)

Every entity query reports a failed read as an error, so no module can show "nothing here" when the read failed.

**Why this priority**: Phases 186 and 193 set this rule, and one hook still breaks it (`useSessionTraces`).

**Independent Test**: One test of the shared query adapter covers the throw, unwrap and default rule. A test of the session traces read shows that a failed read surfaces as an error.

**Acceptance Scenarios**:

1. **Given** the server returns an error for any entity read, **When** a module reads it, **Then** the module sees an error state, not empty data.
2. **Given** the session traces read fails, **When** the trace rail renders, **Then** it shows its error line, not an empty trace.

---

### User Story 3 — The notification bell updates from one entity module (Priority: P2)

A `notification` frame adds the item to the bell's list, bumps the unread count, and makes the notification queries stale. The notification entity owns this, not a feature.

**Why this priority**: It closes the leak of the notification shape into a feature.

**Independent Test**: An entity-level test feeds a frame and reads the list and count back.

**Acceptance Scenarios**:

1. **Given** the bell list is loaded, **When** a notification frame arrives, **Then** the item is first in the list, unread, and the unread count rises by one.
2. **Given** the notification targets a held write, **When** it arrives, **Then** the held-writes query is stale as well.

---

### User Story 4 — Each entity declares its queries once (Priority: P3)

An entity lists its queries in one place, each with a key, a read and the record kinds that make it stale. Adding a query does not mean adding a hook file that repeats the error rule.

**Why this priority**: It removes boilerplate. Nothing changes for the user.

**Independent Test**: The goal and workflow entities are converted first. Their existing widget tests pass unchanged.

**Acceptance Scenarios**:

1. **Given** the goal and workflow entities after conversion, **When** the Doing place renders, **Then** it behaves exactly as before, verified by the existing tests.
2. **Given** the conversion is complete, **When** the source is searched, **Then** the error-throw line exists only in the shared adapter.

### Edge Cases

- **A mutation that changes two record kinds** (deciding a held write changes the held write and its notification) invalidates the union of both kinds' stale sets, with no repeats.
- **Paged lists.** A record kind whose stale set includes a paged list (notifications) re-reads every page shape that list uses, and the notification frame's local insert still applies.
- **Exact keys.** A query key with parameters (loops by state, hypotheses by state and entity) is made stale by its kind's prefix, not by an exact key, so filtered views re-read too.
- **Messages.** A `message` frame keeps re-reading the World set. That broad behaviour is preserved, but it becomes one named entry in the table instead of a list inside a feature.
- **Plugin modules.** A plugin module id never collides with a core record kind; the `module:` prefix stays.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The web client MUST have one staleness table that maps each record kind to the query keys it makes stale. Record kinds include at least loop, goal, goal gate, held write, hypothesis, reminder, workflow, workflow run, notification, procedure, skill, fact, message trace, a `module:<id>` refresh, and the World set after a reply.
- **FR-002**: One function MUST invalidate a record kind, optionally narrowed to one record. Every mutation success, every `refresh` frame, every `notification` frame and every assistant `message` frame MUST call it. No other code may call `invalidateQueries` with a hand-written key list.
- **FR-003**: Every query key MUST come from `queryKeys`. The 13 raw string keys listed in Context MUST be removed.
- **FR-004**: Inserting a notification into the bell list and updating the unread count from a frame MUST live in `entities/notification`. The refresh feature only routes the frame to it.
- **FR-005**: A shared query adapter in `shared/api` MUST own the rule "a failed read throws, success unwraps the data", including each query's empty default. Entity reads MUST go through it.
- **FR-006**: `useSessionTraces` MUST surface a failed read as an error, per phases 186 and 193.
- **FR-007**: Each entity MUST declare its queries and mutations in one module of its `api/` segment, exported from the entity index. One file per hook is no longer required.
- **FR-008**: `features/procedure-review` and `features/review-procedure` MUST be merged into one feature slice. Their single consumer keeps its behaviour.
- **FR-009**: The AGENTS.md ze-web convention ("Query hooks — always in `entities/<name>/api/use<Name>Query.ts`") MUST be rewritten to the new rule, in the same change that lands FR-007. **Doc change for the parent / Docs Steward:** AGENTS.md, ze-web section, "Query hooks" and "Mutations" paragraphs.
- **FR-010**: `entities/query-errors.test.tsx` MUST be replaced by one adapter test plus one table test. No per-hook throw assertions remain.
- **FR-011**: No user-visible change except the fixed staleness (US1) and the error state for session traces (US2).

### Key Entities

- **Record kind**: a kind of stored thing whose change can make views stale: loop, goal, held write, and so on.
- **Staleness table**: the one mapping from record kind to the queries it makes stale.
- **Entity query declaration**: an entity's list of reads, each with a key, a read and its stale kinds.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Exactly one module calls `invalidateQueries` with explicit keys. Today 23 files do.
- **SC-002**: Zero raw string query keys. Today there are 13.
- **SC-003**: The error-throw line appears in exactly one module. Today it appears 53 times.
- **SC-004**: Entity hook files drop from 67 to at most one query module per entity, about 26.
- **SC-005**: US1's loop scenario passes for all three sources: mutation, notification and refresh.
- **SC-006**: All existing ze-web tests pass, and `make typecheck-web` is clean.

## Assumptions

- No backend or frame-shape change.
- Generated SDK functions from `@myguyze/ze-client` stay the transport. The adapter wraps them and does not replace them.
- The broad World re-read after each assistant message stays. Narrowing it is a later choice.

## Out of Scope

- Turn state and the WS store's per-thread maps (phase 205).
- The Module loading, error and empty rendering (phase 218).
