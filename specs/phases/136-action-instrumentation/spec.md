# Feature Specification: Action Instrumentation onto the Contribution Seam

**Feature Branch**: `136-action-instrumentation`  
**Created**: 2026-09-15  
**Status**: Implemented  
**Input**: Instrument concrete action producers against Phase 135's `ActionRecord` ledger. Domain stores remain the source of truth; every completed, attempted, or pending action is represented exactly once in the ledger through an idempotent contribution write.

**Depends on**: Phase 135 — ActionRecord ledger; Phase 124 — Contribution validation and Phase 126 — collision detection. This is rollout step 7 in [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md): action contributes records of what it did, not interpretations of what those records mean.

## Overview

Ze already has domain-specific records for work it performs: workspace runs, sent messages, calendar and reminder changes, goal and workflow execution, and prospecting outreach. They are fragmented, so there is no governed, chronology-correct account of actions across domains.

This phase instruments those concrete producers. Once an action outcome is known, the producer writes its normal domain record and submits one Phase 135 `ActionRecord` observation that cites that record. Phase 135 is append-only: a genuinely observed `pending` state and a later outcome are distinct, causally linked observations, each exactly-once by its own idempotency key. The ledger is an auditable projection, not a replacement domain store and not a second operational history. It records outcome facts only; it does not infer learning, create procedures, rank work, or alter perception delivery.

## User Scenarios & Testing

### User Story 1 — Audit workspace and outbound actions (Priority: P1)

When Ze runs a workspace command or sends an outbound messenger message, the completed attempt appears once in the action ledger with its true outcome, time, context, and a citation to the authoritative workspace run or sent-message record.

**Independent Test**: Exercise a successful and failed workspace run, an idempotent retry, and a successful outbound send. Assert one ledger row per domain record, accurate outcome, and no action row before the result is known.

**Acceptance Scenarios**:
1. **Given** a workspace run succeeds, **When** its terminal result is persisted, **Then** one
   `ActionRecord` is persisted with lifecycle `succeeded` and outcome `success`, after the run
   outcome is known, citing that run.
2. **Given** the same workspace completion callback is delivered twice, **When** instrumentation runs again, **Then** there remains exactly one ledger record for that completed workspace outcome observation.
3. **Given** an outbound send fails before a provider receipt exists, **When** the send attempt has a terminal failure, **Then** one failure record cites the producer-owned attempt/send record and includes available conversation and channel context.

### User Story 2 — Audit calendar and reminder mutations (Priority: P1)

When Ze creates, updates, deletes, or schedules a calendar/reminder item, the ledger accurately reports whether the requested mutation succeeded, failed, was cancelled, remains pending confirmation, or only partially completed.

**Independent Test**: Mock calendar and reminder mutation paths for each applicable terminal state. Assert their action record references the calendar/reminder source record and preserves mutation context.

**Acceptance Scenarios**:
1. **Given** a calendar create completes at the provider, **When** its local domain state is committed, **Then** a single success record cites the calendar mutation/source object.
2. **Given** a mutation requires confirmation and awaits a choice, **When** no provider mutation
   has occurred, **Then** it records a non-terminal lifecycle observation, not `success`.
3. **Given** a multi-step mutation creates one requested item but fails a second, **When** the producer can identify both results, **Then** it records `partial` with a factual summary and references to the available source records.

### User Story 3 — Audit automation and outreach execution (Priority: P1)

When goals, workflows, and prospecting campaigns execute an external or internal action, the ledger makes the finished attempt traceable back to its execution trace or outreach record without changing the domain lifecycle.

**Independent Test**: Complete, fail, cancel, and retry representative goal/workflow steps and prospecting outreach. Assert stable idempotency keys, cited domain rows, context IDs, and one ledger record per attempted producer action.

**Acceptance Scenarios**:
1. **Given** a goal milestone action finishes, **When** its execution trace has an outcome, **Then** exactly one action record cites that trace and carries goal, milestone, session, and message context when available.
2. **Given** a workflow execution is cancelled, **When** cancellation is persisted by the workflow domain, **Then** exactly one `cancelled` action record is created; it is not restated as a failure.
3. **Given** prospecting sends outreach and later retries the same durable outreach record, **When** the callback is replayed, **Then** the ledger does not create a duplicate.

### Edge Cases

- A producer crashes between domain persistence and ledger submission: retry the submission from the same durable source record and idempotency key; do not re-run the side effect merely to fill the ledger.
- A provider request is accepted but its final result is unknown: record the truthful `pending` observation; when it resolves, append one terminal observation with a causal link to pending, as required by Phase 135's immutable ledger.
- A request is cancelled before it starts: record `cancelled` only after cancellation is known and cite the durable request/run where one exists.
- A batch produces mixed outcomes: create one action record for each individually identifiable attempted action; use `partial` only where one durable producer action has multiple requested effects and a mixed result.
- If a producer cannot create or find its required domain record, it MUST NOT fabricate a source citation. Its existing error policy applies and the gap is observable through logs/tests.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST instrument these producers: workspace runs, outbound messenger sends, calendar mutations, reminder mutations, goal execution, workflow execution, and prospecting outreach.
- **FR-002**: Plugin and domain stores MUST remain the source of truth for their own actions. An `ActionRecord` MUST cite the producer-owned durable record and MUST NOT replace, mirror as a writable operational ledger, or drive recovery of that store.
- **FR-003**: Every instrumented action observation MUST use one stable idempotency identity derived from the durable producer record, action kind, and observed lifecycle/outcome. Repeated delivery of that observation MUST converge on exactly one ledger record.
- **FR-004**: An action record MUST be created only after the producer knows a factual outcome, except that an explicitly persisted awaiting/accepted-but-unresolved attempt MAY be recorded as `pending`.
- **FR-005**: Producers MUST use Phase 135's closed lifecycle and outcome vocabulary: a pending
  observation is `started` or `in_progress` with no outcome; terminal observations use `success`,
  `failure`, `cancelled`, `partial`, `timeout`, or `unknown` as applicable. `cancelled` MUST NOT
  be collapsed into `failure`.
- **FR-006**: A `pending` action that later resolves MUST append one terminal ActionRecord causally linked to the pending observation, preserving chronology and final observed time. It MUST NOT duplicate either observation on callback replay.
- **FR-007**: Each action record MUST contain action type, lifecycle and terminal outcome where
  applicable, occurred/append timestamps, actor, producer package, authoritative source reference,
  a factual summary, and available context IDs (`request_id`, `session_id`, `message_id`,
  `thread_id`, `goal_id`, `milestone_id`, `workflow_id`, `workflow_run_id`, `workspace_run_id`,
  `channel_id`, `outreach_id`, or calendar/reminder IDs as relevant).
- **FR-008**: Producers MUST submit action records through Phase 135's validated `ActionRecord` ledger path and the contribution seam using Action's licensed record claim shape. They MUST NOT bypass ledger validation with direct ledger SQL.
- **FR-009**: Domain writes and action instrumentation MUST have an explicit failure posture: never claim `success` before the domain/provider outcome; retry-safe ledger recording after domain persistence; existing domain action behavior remains authoritative if instrumentation fails.
- **FR-010**: Tests MUST prove chronology, idempotency, accurate state mapping, durable source citation, and context propagation for each producer family.
- **FR-011**: This pre-v1 phase MAY hard-cut producer contracts/callbacks needed to carry outcome and context. It MUST NOT retain shims, dual-write two operational histories, or support an old ungated action-record API.
- **FR-012**: This phase MUST NOT add inbound perception instrumentation, rewire `signal_sources()`, derive learning or interpretations from records, create procedures, or change arbitration/ranking/priority behavior.

### Key Entities

- **ActionRecord**: Phase 135 ledger entity representing one immutable producer action observation,
  keyed idempotently; terminal resolution after pending is a new causally linked observation.
- **Producer source record**: The authoritative domain record—such as a workspace run, sent-message attempt, calendar/reminder mutation, execution trace, workflow run, or outreach row—that the ActionRecord cites.
- **Outcome**: A factual terminal result: `success`, `failure`, `cancelled`, `partial`, `timeout`,
  or `unknown`; non-terminal observations have no outcome.
- **Context IDs**: Durable correlation identifiers captured from the initiating turn, automation scope, channel, and producer record where available.

## Success Criteria

- **SC-001**: Dedicated tests demonstrate 100% coverage of the seven named producer families, with at least one representative success and non-success path each.
- **SC-002**: Replaying every instrumented action observation in tests leaves exactly one ActionRecord for that stable observation identity.
- **SC-003**: All action records in producer tests cite a durable domain source record and contain every context ID available at that call site.
- **SC-004**: Tests verify no success record is written before its producer outcome is known, and pending-to-terminal resolution appends one causally linked terminal observation without duplicate delivery.
- **SC-005**: Existing domain-store tests continue to prove producer behavior without treating ActionRecord as the source used for recovery or state transitions.

## Assumptions

- Phase 135 provides the `ActionRecord` type, persistence contract, contribution conversion, uniqueness/upsert behavior, and migration slot. This phase consumes that ledger; it does not redesign it.
- “Exact-one” means one record per durable producer outcome observation, not one record per transport callback or every sub-step in a batch. Phase 135's append-only lifecycle means a durable pending observation and a later terminal observation are two linked observations.
- A factual `partial` result is permitted only when the producer owns one identified action with mixed observable effects; otherwise model separate actions.
- The action contribution is an account of an attempted/observed action, not a `FACT` contribution and not a semantic interpretation.

## Out of Scope

- Inbound messages, ingestion, conversation facts, or any other perception producer
- `signal_sources()` registration or polling rewiring
- Learning, reflection, summaries, semantic interpretation, memory procedures, or skill generation
- Contribution arbitration, collision-resolution policy, PriorityView, push budgets, or priority ranking
- Replacing plugin/domain stores, provider receipts, retry engines, or recovery workflows with ActionRecord
- New user-facing dashboards, REST routes, or WebSocket frames beyond Phase 135’s existing ledger surface
