---
description: "Task list for Action Record Ledger (Phase 135)"
---

# Tasks: Action Record Ledger

**Input**: Design documents from `/specs/phases/135-action-record-ledger/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/action-records.md, quickstart.md

**Tests**: Included — constitution Principle V.

**Organization**: doctrine contract and storage foundation → ledger semantics → reference
producers and recoverable handoff → verification.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can proceed in parallel after its dependencies (different files).
- **[US#]**: User story in spec.md.

---

## Phase 1: Setup and source-boundary audit

- [x] T001 Inspect the workspace-run and outbound-message persistence flows. Record the exact
  durable source record, terminal-state mapping, transaction boundary, and safe summary fields
  for each; do not instrument raw tool traces · workspace + messenger source modules
- [x] T002 Determine the next free `zm` revision and create the migration skeleton owned by
  `ze-memory`; confirm `ze_api/migrate.py` already discovers the memory chain ·
  `core/cognition/ze-memory/ze_memory/migrations/versions/`
- [x] T003 Add failing contract tests proving ACTION currently cannot produce the proposed kind
  and other functions must not produce it · `core/contracts/ze-plugin/tests/test_contribution.py`

## Phase 2: Foundational doctrine and ledger (blocking)

**Purpose**: Make ActionRecord a licensed, validated contribution and persist it exactly once.

- [x] T004 Add `ClaimKind.ACTION_RECORD` to the shared closed claim vocabulary and update all
  exhaustive matching/serialization tests · `core/contracts/ze-agents/ze_agents/claims.py` and
  tests
- [x] T005 Update `SourceFunction.ACTION` licensing to permit only `ACTION_RECORD`; extend
  contribution validation for action payload/kind coherence and action-record evidence checks ·
  `core/contracts/ze-plugin/ze_plugin/contribution.py`
- [x] T006 [P] Define typed `ActionRecord`, `ActionRecordDraft`, `AuthoritativeRef`,
  `ActionContext`, `CausalRef`, `ActionLifecycle`, and `ActionOutcome` plus typed validation
  errors; include actor, producer package, request, and correlation fields without a plugin enum;
  add no Pydantic domain types · `core/cognition/ze-memory/ze_memory/action_records/types.py`
- [x] T007 [P] Add fail-first tests for valid/invalid lifecycle-outcome combinations, one
  authoritative reference, payload coherence, dangling action-record citations, and no Fact
  projection · `core/cognition/ze-memory/tests/action_records/`
- [x] T008 Create the `action_records` schema with immutable columns, doctrine/state/outcome
  checks, unique idempotency key, self-reference FKs, and chronological/reference indexes · next
  `zm` migration
- [x] T009 Implement `ActionRecordStore` and Postgres append/get/list methods. Use atomic
  idempotency conflict handling; reject material mismatch under a reused key; expose no update or
  delete method · `core/cognition/ze-memory/ze_memory/action_records/store.py`
- [x] T010 Implement `submit_action_record` through the existing contribution validation seam;
  bind append as `write=` and provide the action-record existence checker ·
  `core/cognition/ze-memory/ze_memory/action_records/contribution.py`
- [x] T011 Re-export only the producer-safe contribution/types surface from `ze_sdk`; do not
  export an unchecked SQL append · `packages/ze-sdk/ze_sdk/contribution.py` and/or
  `ze_sdk/memory.py`

**Checkpoint**: A valid Action contribution appends exactly one ActionRecord; invalid/unlicensed
submissions persist nothing.

## Phase 3: User Story 1 — durable truthful outcomes

- [x] T012 [P] Add store tests for successful, failed, cancelled, partial, timed-out, unknown,
  started, and in-progress records; assert terminal outcome requirements and append-only behavior ·
  `core/cognition/ze-memory/tests/action_records/`
- [x] T013 [US1] Implement bounded/sanitized summary and failure-code validation. Ensure raw
  command args, message contents, credentials, stack traces, and unbounded output cannot enter
  the ledger · `ze_memory/action_records/`
- [x] T014 [US1] Implement chronological query by `AuthoritativeRef` and `CausalRef`; test
  source identifiers are opaque strings rather than forced UUIDs ·
  `ze_memory/action_records/store.py` and tests

**Checkpoint**: US1 accepts truthful observations and retains no duplicate operational truth.

## Phase 4: User Story 2 — idempotency and causal chain

- [x] T015 [P] Add concurrent-submit tests using mocked asyncpg/store behavior and verify one
  returned row per idempotency key · `core/cognition/ze-memory/tests/action_records/`
- [x] T016 [P] Add retry/correction chain tests: distinct keys append new rows, valid
  `retry_of`/`supersedes` resolve, self/dangling references fail ·
  `core/cognition/ze-memory/tests/action_records/`
- [x] T017 [US2] Implement typed causal-reference serialization/deserialization and validation
  against existing spine checkers plus the ActionRecord store checker ·
  `ze_memory/action_records/`

**Checkpoint**: US2 has database-enforced dedup and inspectable causal history.

## Phase 5: User Story 3 — recoverable failure delivery

- [x] T018 Define and implement the minimal durable handoff/retry boundary where a source record
  commits before ledger append. The handoff stores no second action ledger representation and
  reuses the immutable idempotency key · source-owner package(s) plus `ze-memory`
- [x] T019 [P] Add failure-injection tests: source success + ledger failure retries append only;
  source failure creates failed evidence; uncertain outcome creates unknown; no test reruns a
  side effect · workspace/messenger tests
- [x] T020 [US3] Add structured logging/telemetry for append rejection, transient delivery
  failure, and successful recovery without exposing sensitive payloads · source adapters/handoff

**Checkpoint**: Ledger loss is observable and recoverable, not hidden by a fabricated outcome.

## Phase 6: User Story 4 — reference producers

- [x] T021 [P] Implement the workspace-run adapter after source persistence. Map terminal and
  non-terminal states, stable source ref, sanitized summary, and any causal approval/request
  evidence to ActionRecord · `core/ops/ze-workspace/ze_workspace/`
- [x] T022 [P] Implement one outbound messenger-send adapter after durable sent-message
  persistence. Map source ref and truthful outcome without copying recipient/body detail ·
  `plugins/ze-messenger/ze_messenger/`
- [x] T023 [P] Add workspace adapter tests for success/failure/cancel/timeout/in-progress and
  duplicate delivery · `core/ops/ze-workspace/tests/`
- [x] T024 [P] Add messenger adapter tests for success/failure/unknown and duplicate delivery ·
  `plugins/ze-messenger/tests/`
- [x] T025 [US4] Confirm both source stores remain the operational source of truth and no
  Fact/Signal/episode path now accepts ActionRecord · targeted repository scan and tests

**Checkpoint**: Two independent domains use one ledger contract without a generic event bus.

## Phase 7: Polish and verification

- [x] T026 [P] Verify every new `ClaimKind` switch is exhaustive with a `never`-equivalent
  Python error path where appropriate; update SDK exports and public type tests · contracts/SDK
- [x] T027 [P] Verify no production code adds generic arbitration, a collision winner/resolver,
  `signal_sources()` rewiring, Fact-derived action evidence, dual write, or dual read · repo scan
- [x] T028 Run the suites in quickstart: `make test-plugin`, `make test-memory`,
  `make test-workspace`, `make test-messenger`, and `make lint` · repo root
- [x] T029 Re-read migration downgrade/upgrade behavior and verify all constraints/indexes plus
  concurrent idempotency behavior against the test database when available · repo root
- [x] T030 Update this feature's status/checklist only after every task and verification succeeds;
  do not alter `specs/README.md` unless separately directed · feature directory only

## Dependencies & Execution Order

- T001–T003 precede foundation work.
- T004–T011 block all producer wiring.
- T012–T014 and T015–T017 may proceed after T009–T010.
- T018–T020 require the stable store/idempotency contract.
- T021–T024 require source audit plus handoff semantics; they can run in parallel.
- T026–T030 are last.

## MVP

T001 → T004–T011 → T012–T017 → T021/T023: one validated, idempotent workspace ActionRecord
with truthful terminal outcomes. Messenger and recoverable handoff complete the release scope.
