# Feature Specification: Action Record Ledger

**Feature Branch**: `135-action-record-ledger`  
**Created**: 2026-09-15  
**Status**: Implemented  
**Input**: Create a `ze-memory`-owned append-only cross-domain ActionRecord ledger. Rows cite plugin-owned authoritative records. An action record is action evidence and a first-class `Contribution` variant, not a user-memory `Fact`.

**Governed by**: [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md) (Action may produce records of what it did), [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md) (rollout step 7), and [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md) (no compatibility layer, dual write, or dual read). Depends on Phases 124, 126, 133, and 134.

## Overview

Ze currently records domain outcomes in the package that owns each operation: a workspace run,
outbound channel message, calendar mutation, workflow run, or goal execution trace. Those
records are authoritative for domain behavior, but they do not share a durable, queryable account
of **what Ze actually attempted, when, why, with what evidence, and how it ended**.

This feature adds an append-only `ActionRecord` ledger owned by `ze-memory`. Each record is a
cross-domain evidence entry that cites, but never copies or replaces, the plugin-owned source of
truth. It is submitted through the contribution seam as `SourceFunction.ACTION` and a new,
closed `ClaimKind.ACTION_RECORD`. This is the smallest doctrine and contribution-contract hard
cut that gives Action a licensed output. It deliberately does not choose general arbitration,
change collision resolution, or rewire `signal_sources()`.

An ActionRecord is not a `Fact`: it is not retrieved as user memory, does not participate in fact
contradiction, fact decay, user-profile synthesis, or memory-feed fact review. It is operational
evidence that other later work may cite.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Durable record of an action outcome (Priority: P1)

When Ze performs a side effect through a supported domain, it appends one immutable record that
links back to the authoritative domain record and states the outcome honestly.

**Independent Test**: Submit a successful workspace action with a stable idempotency key. Assert
one action-ledger row, `ACTION` source function, `ACTION_RECORD` kind, correct authoritative
reference and evidence, and no `memory_facts` write.

**Acceptance Scenarios**:
1. **Given** a completed supported action with an authoritative record, **When** its outcome is
   recorded, **Then** exactly one immutable ActionRecord cites that authoritative record.
2. **Given** an action accepted but not yet terminal, **When** it is recorded, **Then** its state
   is `started` or `in_progress`, with no fabricated terminal outcome.
3. **Given** a terminal success, failure, cancellation, or timeout, **When** it is recorded,
   **Then** the terminal state and result classification are preserved without rewriting history.

### User Story 2 — Safe retries and causal evidence (Priority: P1)

When an action is retried or its completion callback is delivered more than once, the ledger does
not invent duplicate evidence. It preserves causal links from the action request to the resulting
domain record and any input evidence.

**Independent Test**: Submit the same idempotency key twice concurrently and then submit a retry
with a new key plus `retry_of`. Assert one row for the duplicate delivery, two rows for the
retry chain, and valid references on both.

**Acceptance Scenarios**:
1. **Given** duplicate delivery of the same logical transition, **When** both submissions use the
   same idempotency key, **Then** only one ActionRecord is appended and both callers receive it.
2. **Given** a deliberate retry, **When** it has a distinct idempotency key, **Then** it appends a
   new record that cites the prior record through `retry_of`.
3. **Given** source facts, loops, goals, workflow steps, or an approval that caused the action,
   **When** the action record is submitted, **Then** its causal/evidence references are retained
   and validated according to their reference kind.

### User Story 3 — Failure evidence remains honest and observable (Priority: P1)

When an action fails after the side effect was attempted, Ze retains an honest failure record
instead of silently dropping it or turning it into a remembered fact.

**Independent Test**: Simulate an authoritative workspace run that exits non-zero and a ledger
write that temporarily fails. Assert the run remains authoritative, a recoverable pending
ledger handoff can be retried idempotently, and no success record is emitted.

**Acceptance Scenarios**:
1. **Given** a known failed domain action, **When** the ledger accepts its result, **Then** it
   appends `failed` evidence with a sanitized failure code/summary and authoritative reference.
2. **Given** the domain action succeeds but ledger append initially fails, **When** delivery is
   retried, **Then** the eventual record is unique and retains the real outcome.
3. **Given** an action's outcome cannot be established, **When** execution stops, **Then** the
   record is `unknown` rather than claimed successful or failed.

### User Story 4 — Domains retain their own source of truth (Priority: P2)

Plugin and core domain stores continue to own operational detail. The ledger is a thin
cross-domain citation layer, not a polymorphic replacement table or a new generic event bus.

**Independent Test**: Record representative workspace and messenger actions. Assert domain
details remain in their source rows, the ledger contains only stable normalized metadata and
references, and Fact/Signal ingestion behavior is unchanged.

## Edge Cases

- A source record may be committed while the ledger is temporarily unavailable. The authoritative
  action is never rolled back solely to make the ledger atomic; delivery must be recoverable and
  idempotent.
- An action may be cancelled before a side effect starts, after it starts, or after an uncertain
  remote response. States distinguish `cancelled` from `unknown`; neither implies success.
- Source systems may have non-UUID identifiers. `authoritative_ref` therefore uses
  `domain` + opaque `record_id`, while cross-spine `EvidenceRef` stays UUID-backed.
- Sensitive command arguments, message bodies, tokens, raw stack traces, and unbounded tool
  output are never copied into the ledger. Store a bounded, sanitized summary or source link.
- Correction is append-only: an incorrect or superseded earlier record is not mutated or deleted;
  a later correcting record cites it with `supersedes`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST add `ClaimKind.ACTION_RECORD` and license it only to
  `SourceFunction.ACTION`; ACTION's current empty license MUST be removed in the same hard cut.
- **FR-002**: The system MUST define `ActionRecord` as a first-class `Contribution` payload and
  persist it only after contribution validation. It MUST NOT model it as `Fact`, `Signal`,
  `OpenLoop`, or a user-memory episode.
- **FR-003**: `ze-memory` MUST own an append-only `action_records` table and typed store; each
  row MUST cite exactly one plugin/core authoritative domain record by `(domain, record_id)`.
- **FR-004**: Each ActionRecord MUST include a stable id, idempotency key, action type, actor,
  producer plugin/core package, lifecycle state, occurred-at timestamp, source function,
  provenance, confidence, target face, bounded summary, authoritative reference, request context,
  and optional causal/evidence references.
- **FR-005**: The store MUST enforce idempotency with a unique key. Repeated delivery of the same
  logical transition MUST return the existing record and MUST NOT append a duplicate.
- **FR-006**: A retry or correction MUST use a new idempotency key and append a new record that
  cites `retry_of` or `supersedes`; existing rows MUST NOT be updated for lifecycle progression.
- **FR-007**: Lifecycle state MUST be one of `started`, `in_progress`, `succeeded`, `failed`,
  `cancelled`, `partial`, `timed_out`, or `unknown`; terminal states MUST never be represented as
  success by omission. A terminal result MUST contain an outcome classification.
- **FR-008**: Action records MUST retain failure evidence as bounded, sanitized metadata. A ledger
  append failure MUST be observable and retriable without re-executing the domain action.
- **FR-009**: Causal/evidence references MUST support existing spine evidence and action-record
  citations; references requiring validation MUST reject dangling ids before append.
- **FR-010**: Initial implementation MUST wire at least workspace runs and one outbound
  communication action as reference producers, while preserving their existing stores as
  authoritative. Additional domains follow the same contract, not bespoke ledger schemas.
- **FR-011**: The ledger MUST provide a read-only internal query surface by authoritative
  reference, causal reference, and chronological order. A public REST/UI surface is deferred.
- **FR-012**: This phase MUST NOT introduce generic contribution arbitration, alter collision
  resolution semantics, or rewire `signal_sources()` polling.
- **FR-013**: This phase is a pre-v1 hard cut: no compatibility action-license map, no
  Fact-derived action records, no dual-write to an alternate ledger, and no dual-read fallback.

### Key Entities

- **ActionRecord**: immutable action evidence submitted by the Action function.
- **AuthoritativeRef**: `(domain, record_id)` pointer to the owning domain's source record.
- **Causal references**: typed citations explaining what initiated, authorized, retried, or
  superseded the action.
- **Action lifecycle**: immutable observations of the action's execution state.

## Success Criteria *(mandatory)*

- **SC-001**: Dedicated tests show 100% of supported producers append only one record for duplicate
  idempotency-key delivery, including concurrent delivery.
- **SC-002**: Dedicated tests show 100% of successful, failed, cancelled, partial, timed-out, and
  unknown sample outcomes preserve their truthful state and never write a `memory_facts` row.
- **SC-003**: Every tested record has exactly one authoritative reference, actor, producer,
  request context when available, and all required causal references are queryable from the
  ledger.
- **SC-004**: An injected transient ledger failure can be retried without rerunning the domain
  side effect and without duplicate records.
- **SC-005**: Existing contribution, fact-memory, signal-source, and collision-detection tests
  remain green with no generic arbitration or polling rewiring.

## Assumptions

- `Provenance` describes how the action evidence was known; direct executor observation normally
  uses `prompt_supplied` only when explicitly supplied, otherwise the implementation will select
  a doctrine-approved existing value with the producer contract. This phase does not add a
  provenance enum member.
- A source domain must expose a stable record id before it can become a producer.
- An outbox/handoff mechanism may be introduced for reliable delivery, but it is not a second
  ledger and does not duplicate the action record.

## Out of Scope

- Generic cross-function contribution arbitration or collision resolution.
- `signal_sources()` delivery/polling redesign.
- Replacing plugin/core domain action stores, their APIs, or their detailed execution journals.
- Public REST routes, web pages, timeline UX, action replay, or user-facing notifications.
- Recording every existing tool invocation in the first release.
