---

description: "Task list for Proactive/Concurrency Hardening Sweep"
---

# Tasks: Proactive/Concurrency Hardening Sweep

**Input**: Design documents from `/specs/phases/113-hardening-sweep/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Included and REQUIRED — constitution principle V (Test Discipline) is
non-negotiable for this project; every task group below writes/extends tests before
implementation.

**Organization**: Tasks are grouped by user story. The three stories touch disjoint
packages/tables (confirmations in `ze-core`+`ze-api`, budget in `ze-core`+`ze-api`
config, push-log in `ze-proactive`+`ze-worldstate`) and share no code — each is
independently implementable and shippable in isolation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Existing monorepo layout (see plan.md Project Structure) — `core/ze-core/`,
`core/ze-proactive/`, `core/ze-worldstate/`, `apps/ze-api/`. No new packages.

---

## Phase 1: Setup

**Purpose**: Confirm a clean baseline before touching shared migration chains.

- [X] T001 Run `make db-up`, `make migrate`, `make lint`, and `make test-core test-proactive test-worldstate test-api` from repo root; confirm all green before any change in this feature (baseline for later diffing test failures introduced by this work).
- [X] T002 [P] Confirm next-free migration revision IDs are still `zc025` (chain head `zc024_query_perf_indexes.py` in `core/ze-core/ze_core/migrations/versions/`) and `zpro003` (chain head `zpro002_notifications.py` in `core/ze-proactive/ze_proactive/migrations/versions/`) — re-check `ls` output in case other work landed on `main` since planning; adjust the IDs used in T007 and T026 if a newer revision now exists.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cross-story blocking work.

**None required.** Per plan.md's Structure Decision, the three stories are narrow,
independent changes to disjoint files and tables with no shared new abstraction. Proceed
directly to Phase 3 once Phase 1 is green.

---

## Phase 3: User Story 1 - No lost confirmation gates (Priority: P1) 🎯 MVP

**Goal**: A second confirmation gate opened on the same conversation thread before the
first is answered must not overwrite the first, in storage or in the WS server's
in-memory state, and each gate's timeout must only ever affect its own row.

**Independent Test**: Per quickstart.md §1 — open two confirmation gates on the same
thread back-to-back, verify both rows exist in `pending_confirmations`, resolve them out
of order, confirm neither resolution nor either gate's timeout affects the other.

### Tests for User Story 1

> Write these first; confirm they fail against the current (pre-fix) code before implementing.

- [X] T003 [P] [US1] Extend `core/ze-core/tests/conversation/test_confirmation_store.py` with cases: two `save()` calls with the same `thread_id` but distinct `request_id`s both persist as separate rows; `get_pending_for_thread()` returns a list containing both; `get_pending(request_id)` returns the correct single row; `clear(thread_id, request_id)` deletes only the matching row, leaving the other's row and `expires_at` untouched.
- [X] T004 [P] [US1] Add `apps/ze-api/tests/api/test_ws.py` (or a new adjacent test module in `apps/ze-api/tests/api/`) case simulating two confirmation-triggering turns on one thread before either is answered: assert two distinct `{"type": "confirmation", "id": ...}` frames are sent, `pending_configs` (or its test-visible equivalent) holds both entries keyed by their own `request_id`, and resolving one via a `{"type": "confirm", "id": ..., "choice": ...}` frame does not affect the other's stored config.

### Implementation for User Story 1

- [X] T005 [US1] Write Alembic migration `core/ze-core/ze_core/migrations/versions/zc025_confirmations_request_id_key.py` (revision `zc025`, `down_revision = "zc024"`): `ALTER TABLE pending_confirmations DROP CONSTRAINT pending_confirmations_pkey; ALTER TABLE pending_confirmations ADD PRIMARY KEY (request_id); CREATE INDEX IF NOT EXISTS ix_pending_confirmations_thread_id ON pending_confirmations (thread_id);` with a symmetric `downgrade()` per contracts/pending-confirmation-store.md.
- [X] T006 [US1] Rewrite `core/ze-core/ze_core/conversation/confirmations/store.py`: `save()` uses `ON CONFLICT (request_id) DO UPDATE`; `get_pending_for_thread(thread_id) -> list[dict]` (was `dict | None`) returns all non-expired rows for the thread; add `get_pending(request_id) -> dict | None`; `clear(thread_id, request_id) -> bool` deletes only the row matching both.
- [X] T007 [US1] Rekey `pending_configs` in `apps/ze-api/ze_api/api/websocket/endpoint.py` from `dict[str, dict]` (`thread_id -> config`) to `dict[str, dict]` (`request_id -> config`) plus a derived `dict[str, set[str]]` (`thread_id -> {request_id, ...}`) maintained alongside every insert/pop; update the three call sites currently doing `pending_configs[thread_id] = result` / `.get(thread_id)` / `.pop(thread_id, None)` (lines ~91-124, ~140-149, ~176-217 per current file) to route through `request_id`.
- [X] T008 [US1] Update `apps/ze-api/ze_api/api/websocket/confirmation.py`: `handle_confirm` passes the already-extracted `request_id` (`data.get("id", "")`) into `confirmation_store.clear(thread_id, request_id)` instead of `clear(thread_id)`; `confirmation_timeout(...)` gains a `request_id: str` parameter and calls `confirmation_store.clear(thread_id, request_id)`.
- [X] T009 [US1] Update the `confirmation_store.clear(effective_thread_id)` call in `apps/ze-api/ze_api/api/websocket/turns.py` (~line 125) to pass the specific `request_id` of the gate being cleared at that point in the flow (trace the call site's context to identify which gate this is — it is the gate just opened in that same function, not an arbitrary thread-scoped one).
- [X] T010 [US1] Wherever `confirmation_timeout(...)` is scheduled as a background task (search callers of `confirmation.py:confirmation_timeout`), pass the `request_id` of the specific gate the timeout guards, matching the new signature from T008.
- [X] T011 [US1] Run `make migrate`; manually verify via `psql` (or the existing test fixture pattern) that pre-existing `pending_confirmations` rows survive the `ALTER TABLE` with no data loss (each row already has a populated `request_id`).
- [X] T012 [US1] Run `make test-core` and `make test-api` and `make lint`; fix until green, including T003/T004.

**Checkpoint**: User Story 1 is independently complete — confirmation gates on the same
thread can coexist, resolve, and time out without clobbering each other.

---

## Phase 4: User Story 2 - Spend cannot run away mid-session (Priority: P2)

**Goal**: An opt-in per-session and/or per-day spend budget, checked in real time
(token-estimated, not waiting for cost reconciliation) inside the existing
`capability_check` graph node, holds further costly execution via the existing
`AWAIT_CONFIRMATION` gate path rather than proceeding silently.

**Independent Test**: Per quickstart.md §2 — configure a low `budget.session_limit_usd`,
drive a turn past it, confirm a confirmation frame (not silent execution, not a hard
block) states current spend and the limit; remove the config and confirm no regression.

### Tests for User Story 2

> Write these first; confirm they fail before implementing.

- [X] T013 [P] [US2] Create `core/ze-core/tests/telemetry/test_pricing.py`: `estimate_cost_usd(model, prompt_tokens, completion_tokens)` returns the correct value for a listed model, and falls back to `DEFAULT_PRICING` for an unlisted model slug.
- [X] T014 [P] [US2] Create `core/ze-core/tests/telemetry/test_budget.py`: `SpendBudgetChecker.check(session_id)` against a mocked `CostStore`/pool — (a) both limits `None` short-circuits with no query and `within_budget=True`; (b) session spend at/over `session_limit_usd` returns `within_budget=False, scope="session"`; (c) daily spend at/over `daily_limit_usd` returns `within_budget=False, scope="daily"`; (d) spend under both limits returns `within_budget=True`.
- [X] T015 [P] [US2] Extend `core/ze-core/tests/orchestration/nodes/test_execution.py` (or add `core/ze-core/tests/orchestration/nodes/test_capability_check_budget.py`) with a case where `CapabilityGate.evaluate()` alone would return `EXECUTE` but a mocked `budget_checker.check()` returns `within_budget=False` — assert the node's final `gate_decision` is `AWAIT_CONFIRMATION` (strictest-wins), and a case with `budget_checker=None` in `configurable` behaves exactly as before (regression, FR-007).

### Implementation for User Story 2

- [X] T016 [P] [US2] Create `core/ze-core/ze_core/telemetry/pricing.py`: `MODEL_PRICING: dict[str, tuple[float, float]]` seeded from the model slugs in `core/ze-core/ze_core/openrouter/context_windows.py` and `apps/ze-api/config/config.yaml` (prompt $/1M, completion $/1M, sourced from current published OpenRouter pricing — comment the table with the source/date, mirroring `context_windows.py`'s own docstring convention), `DEFAULT_PRICING` fallback tuple, and `estimate_cost_usd(model, prompt_tokens, completion_tokens) -> float`.
- [X] T017 [P] [US2] Create `core/ze-core/ze_core/telemetry/budget.py`: `SpendBudgetConfig` dataclass (`session_limit_usd: float | None`, `daily_limit_usd: float | None`), `BudgetStatus` dataclass (`within_budget: bool`, `scope: Literal["session","daily"] | None`, `current_spend_usd: float`, `limit_usd: float | None`), `SpendBudgetChecker` class per contracts/spend-budget-gate.md.
- [X] T018 [US2] Add session-scoped and daily-scoped aggregate query methods to `core/ze-core/ze_core/telemetry/postgres.py`'s `PostgresCostStore` (e.g. `fetch_session_usage(session_id) -> list[dict]`, `fetch_daily_usage() -> list[dict]`, each returning `model`/`prompt_tokens`/`completion_tokens` rows from `llm_cost_log`) and extend the `CostStore` Protocol in `core/ze-core/ze_core/telemetry/store.py` accordingly; `SpendBudgetChecker` (T017) calls these and applies `estimate_cost_usd` per row.
- [X] T019 [US2] **(remediation for analysis finding G2)** Implement the same `fetch_session_usage`/`fetch_daily_usage` methods (matching the `CostStore` Protocol extended in T018) on `SQLiteCostStore` in `core/ze-core/ze_core/telemetry/sqlite.py` — it is a real, exported, tested alternate `CostStore` implementation (see `core/ze-core/tests/telemetry/test_telemetry.py`) used for local/dev deployments without Postgres, and `SpendBudgetChecker` must not raise `AttributeError` when constructed against it. Extend `test_telemetry.py` with cases asserting both new methods return correct session/day token aggregates against a SQLite-backed store. Depends on T018 (Protocol shape must be finalized first).
- [X] T020 [US2] Add an opt-in `budget:` block (`session_limit_usd: null`, `daily_limit_usd: null`) to `apps/ze-api/config/config.yaml`, and wire construction of `SpendBudgetChecker` (or `None` when both limits are null) into `apps/ze-api/ze_api/container.py` alongside the existing `capability_gate` wiring (~line 132/443), passed into the graph's `configurable` dict as `"budget_checker"`.
- [X] T021 [US2] Update `capability_check` in `core/ze-core/ze_core/orchestration/nodes/execution.py`: read `budget_checker` from `config["configurable"].get("budget_checker")`; when present, call `await budget_checker.check(session_id=...)`, append `GateDecision.AWAIT_CONFIRMATION` to the strictest-wins comparison when `not status.within_budget`, and stash the resulting `BudgetStatus` onto the returned state dict (e.g. `"budget_status"`) for T022 to consume.
- [X] T022 [US2] In `draft_response` (`core/ze-core/ze_core/orchestration/nodes/execution.py:91`), when `state.get("budget_status")` is present and `not within_budget`, include the current spend and configured limit in the confirmation prompt text sent to the user (per spec FR-006/SC-004 — the message must be self-sufficient, no log-digging required).
- [X] T023 [US2] Run `make test-core` and `make test-api` and `make lint`; fix until green, including T013–T015 and T019.

**Checkpoint**: User Story 2 is independently complete — configuring a budget holds
execution via the existing confirmation gate; leaving it unconfigured changes nothing;
budget checking works against both Postgres- and SQLite-backed cost stores.

---

## Phase 5: User Story 3 - No duplicate proactive nudges for the same open loop (Priority: P3)

**Goal**: Two concurrent runs of `PushSweepJob` (or any concurrent caller reaching
`LoopSurfacer`'s push path) for the same open loop can never both send a notification —
the database write, not the pre-check, is the arbiter of exclusivity — and a notifier
failure after a successful claim can never silently swallow a notification the user was
supposed to receive.

**Independent Test**: Per quickstart.md §3 — force two concurrent `PushSweepJob.run()`
calls against a loop that qualifies for a push; assert exactly one `notifier.push(...)`
call and exactly one `push_log` row for that loop's `idempotency_key`.

### Tests for User Story 3

> Write these first; confirm they fail before implementing.

- [X] T024 [P] [US3] Extend `core/ze-proactive/tests/test_push_log_store.py` (or create it if absent) with: `try_claim()` first call returns `True` and inserts a row; a second `try_claim()` call with the same `(event_type, idempotency_key)` returns `False` and does not raise; a `try_claim()` call with `idempotency_key=None`-equivalent event types (i.e. plain `log()` calls) is unaffected by the new unique index; `release_claim()` (T027) deletes a previously claimed row so a subsequent `try_claim()` for the same key succeeds again.
- [X] T025 [P] [US3] Extend `core/ze-worldstate/tests/jobs/test_push_sweep.py` with: (a) a concurrency test — two `PushSweepJob.run()` invocations run via `asyncio.gather` against shared loop-store/surfacer state where the loop qualifies for exactly one push; assert the mocked notifier's `push()` is called exactly once total across both runs; (b) **(remediation for analysis finding G1)** a notifier-failure test — the mocked notifier's `push()` raises on a loop that was successfully claimed; assert the claim is rolled back (`release_claim`/equivalent called, or the `push_log` row removed) so a subsequent sweep run can retry that loop, and assert the exception does not abort processing of other loops in the same sweep.

### Implementation for User Story 3

- [X] T026 [US3] Write Alembic migration `core/ze-proactive/ze_proactive/migrations/versions/zpro003_push_log_idempotency.py` (revision `zpro003`, `down_revision = "zpro002"`): `ALTER TABLE push_log ADD COLUMN IF NOT EXISTS idempotency_key TEXT; CREATE UNIQUE INDEX IF NOT EXISTS ux_push_log_event_idempotency ON push_log (event_type, idempotency_key);` with a symmetric `downgrade()` per contracts/push-log-idempotency.md.
- [X] T027 [US3] Add `try_claim(event_type, idempotency_key, payload=None) -> bool` to `core/ze-proactive/ze_proactive/push_log_store.py`: attempts the insert with `idempotency_key`, returns `True` on success, catches `asyncpg.UniqueViolationError` and returns `False` (never raises for the expected "lost the race" case). Leave the existing `log()` method untouched for all other callers. **(remediation for analysis finding G1)** Also add `release_claim(event_type, idempotency_key) -> None`, deleting the row matching both columns — used to roll back a claim when the notification that claim was guarding turns out not to have been delivered.
- [X] T028 [US3] Replace `LoopSurfacer.log_push()` with `claim_push(loop_id, rationale) -> bool` in `core/ze-worldstate/ze_worldstate/surfacing.py`, calling `self._push_log.try_claim(PUSH_EVENT_KEY, idempotency_key=str(loop_id), payload=rationale)`. Add a corresponding `release_push_claim(loop_id) -> None` calling `self._push_log.release_claim(PUSH_EVENT_KEY, idempotency_key=str(loop_id))` for T029's rollback path.
- [X] T029 [US3] Update `PushSweepJob.run()` in `core/ze-worldstate/ze_worldstate/jobs/push_sweep.py`: after the existing re-check of loop state (post-`passes_push_bar`), call `claim_push(loop.id, loop.drift_rationale)`; if the claim returns `False`, `log.info("open_loop_push_already_claimed", loop_id=...)` and `continue` without notifying. On a successful claim, call `self._notifier.push(...)` **inside a `try`/`except`**: on success, `log.info("open_loop_pushed", ...)` as before; on any exception from `notifier.push`, call `release_push_claim(loop.id)` (T028) so a future sweep can retry this loop, `log.warning("open_loop_push_notify_failed", loop_id=..., error=...)` distinctly from the already-claimed skip path, and re-raise or swallow consistent with how the surrounding job-runner already handles a single item's exception without aborting the rest of the sweep's loop iteration (verify this against the existing `run()` loop structure/error-handling convention in this job before deciding — do not let one loop's notify failure silently stop other loops in the same sweep from being evaluated).
- [X] T030 [US3] Grep the codebase for any other callers of `LoopSurfacer.log_push` (there should be none outside `push_sweep.py` per current usage, but confirm) and update them to the new `claim_push`/`release_push_claim` contract.
- [X] T031 [US3] Run `make migrate`; run `make test-proactive` and `make test-worldstate` and `make lint`; fix until green, including T024–T025.

**Checkpoint**: User Story 3 is independently complete — concurrent sweep runs cannot
double-notify on the same loop, a notifier failure after a successful claim cannot
silently drop a notification either (the claim is rolled back for retry), and existing
single-run cooldown/budget behavior is unchanged (regression-checked by the untouched
portions of `test_push_sweep.py`).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and full-suite validation once all three stories land.

- [X] T032 Walk through `specs/phases/113-hardening-sweep/quickstart.md` end-to-end against a running `make dev` instance (all three manual scenarios), confirming pass criteria for SC-001 through SC-006.
- [X] T033 [P] Update `specs/README.md`'s feature index with the row for `113-hardening-sweep`, and add a Phase 113 row to the Phase status table in `CLAUDE.md` (per constitution I — status updated in the same commit as implementation).
- [X] T034 Update `specs/phases/113-hardening-sweep/spec.md`'s `**Status**: Draft` header to `Implemented` in the same commit as the final implementation change (constitution I).
- [X] T035 Run `make test-all` and `make lint` from repo root; confirm fully green before considering this phase done (constitution V, Definition of Done).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — run first.
- **Foundational (Phase 2)**: Empty — no blocking work, proceed straight to Phase 3.
- **User Stories (Phase 3, 4, 5)**: Each depends only on Phase 1 completing. They touch
  disjoint files/tables (confirmed in plan.md's Project Structure) and can proceed in
  any order, or fully in parallel if staffed by different people/sessions.
- **Polish (Phase 6)**: Depends on all three user stories being complete (T032/T035
  validate the whole feature together; T033/T034 are documentation bookkeeping that only
  makes sense once the implementation is final).

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on US2 or US3. Touches `core/ze-core/ze_core/conversation/`, its `zc` migration chain, and `apps/ze-api/ze_api/api/websocket/`.
- **User Story 2 (P2)**: No dependency on US1 or US3. Touches `core/ze-core/ze_core/telemetry/`, `core/ze-core/ze_core/orchestration/nodes/execution.py` (same file US1 does NOT touch — US1 only touches `apps/ze-api` websocket handlers and the confirmation store, not `execution.py`), and `apps/ze-api/config/config.yaml` + `container.py`. Note: US2's budget-triggered `AWAIT_CONFIRMATION` gates flow through the same `pending_confirmations`/`confirmation_timeout` machinery US1 hardens — no file overlap, but shipping US2 before US1 leaves budget-triggered gates exposed to the pre-existing clobber bug like any other gate (acceptable, not a blocker).
- **User Story 3 (P3)**: No dependency on US1 or US2. Touches `core/ze-proactive/ze_proactive/push_log_store.py`, its `zpro` migration chain, and `core/ze-worldstate/ze_worldstate/{surfacing.py,jobs/push_sweep.py}`.

No cross-story file overlap exists — all three can be implemented, tested, and merged
independently in any order.

### Within Each User Story

- Tests (T003-T004 / T013-T015 / T024-T025) MUST be written and confirmed failing before
  their corresponding implementation tasks.
- Migration before store/module changes that depend on the new schema (T005→T006;
  T026→T027).
- Store/module changes before the call sites that consume them (T006→T007-T009;
  T016-T019→T020-T022; T027→T028-T029).
- T019 (SQLite parity) depends on T018 (Protocol extension) but not on T020-T022.
- T028's `release_push_claim` addition depends on T027's `release_claim` addition; T029's
  rollback call depends on both.
- Each story's final task runs its package test suites + lint to green before the
  story's checkpoint is considered met.

### Parallel Opportunities

- T001 and T002 can run together (Setup).
- Within US1: T003 and T004 in parallel (different files/packages).
- Within US2: T013, T014, T015 in parallel (different test files); T016 and T017 in
  parallel (different new files) — T018 depends on T017's `SpendBudgetChecker` shape;
  T019 can run in parallel with T020 once T018 lands (different files — `sqlite.py` vs.
  `config.yaml`/`container.py`).
- Within US3: T024 and T025 in parallel (different packages).
- **Once Phase 1 is done, all three user story phases (3, 4, 5) can be worked in
  parallel** — by three different sessions/developers, or sequentially by one person in
  any order — since they share no files.

---

## Parallel Example: Kicking off all three stories at once

```bash
# After Phase 1 (T001-T002) completes, launch all three story leads together:
Task: "US1 — rekey pending_confirmations + pending_configs (T003-T012)"
Task: "US2 — spend budget gate in capability_check (T013-T023)"
Task: "US3 — push_log idempotent claim (T024-T031)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 3: User Story 1 (T003–T012).
3. **STOP and VALIDATE**: Run quickstart.md §1 against a live `make dev` instance.
4. This alone closes the highest-severity finding from the audit (active data loss on
   concurrent confirmation gates) — a reasonable standalone ship point if the other two
   stories need more review time.

### Incremental Delivery

1. Setup → Phase 3 (US1) → validate → ship.
2. Phase 4 (US2) → validate → ship (new opt-in config, zero behavior change for
   anyone who doesn't set it).
3. Phase 5 (US3) → validate → ship (closes the lowest-severity, already
   partially-mitigated gap — and now also closes the notifier-failure rollback gap
   found in review, T025b/T029).
4. Phase 6 (Polish) once all three are in.

### Solo Session Strategy

Given no cross-story file overlap, a single implementer can also do all three stories
back-to-back in priority order (US1 → US2 → US3) within one sitting without needing to
stash/rebase between them, then do Phase 6 once at the end.

---

## Notes

- [P] tasks touch different files with no unmet dependencies.
- [Story] labels map every implementation task to spec.md's User Story 1/2/3.
- Tests are mandatory here (constitution V), not optional — every story's test task(s)
  must fail before its implementation tasks land, then pass after.
- Commit after each task or logical group; each user story is independently revertable
  without affecting the other two.
- Re-verify migration revision IDs (T002) if `main` has moved since this tasks.md was
  generated — do not hardcode past what T002 confirms.
- T019, T027/T028 (partial), and T029 were added/expanded during `/speckit-analyze`
  remediation for findings G2 and G1 respectively — see the analysis report in
  conversation history for full rationale. No spec.md/plan.md changes were needed; both
  fixes are scoped entirely within existing FR-005/FR-008/FR-009 coverage.
