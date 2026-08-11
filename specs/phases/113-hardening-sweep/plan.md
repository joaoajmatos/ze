# Implementation Plan: Proactive/Concurrency Hardening Sweep

**Branch**: `113-hardening-sweep` | **Date**: 2026-08-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/113-hardening-sweep/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Three independent reliability fixes bundled as one phase: (1) rekey `pending_confirmations`
(DB) and the in-process `pending_configs` dict (`ze_api/api/websocket/endpoint.py`) from
`thread_id` to `request_id`, so a second confirmation gate on the same thread can never
overwrite or be clobbered-by-timeout of an earlier one; (2) add a real-time, token-estimated
spend check inside the existing `capability_check` graph node, gated by an opt-in
`budget:` config block, that routes to `AWAIT_CONFIRMATION` when a session/day budget
would be exceeded, reusing the existing `GateDecision`/gate-node wiring rather than adding
new graph nodes; (3) close the `passes_push_bar()`/`log_push()` check-then-act race in
`LoopSurfacer`/`PushSweepJob` with a DB-enforced uniqueness constraint on `push_log`,
so two concurrent sweep runs can't both pass the bar and both write for the same loop.

## Technical Context

**Language/Version**: Python 3.12 (backend), async-only I/O throughout.

**Primary Dependencies**: FastAPI + WebSocket (`apps/ze-api`), LangGraph (`ze-core`
orchestration), asyncpg (`ze-core`, `ze-proactive`, `ze-worldstate`), Alembic (raw SQL
migrations, no ORM).

**Storage**: PostgreSQL. Affected tables: `pending_confirmations` (owned by `ze-core`,
`zc` chain, migration `zc017`), `push_log` (owned by `ze-proactive`, `zpro` chain,
migration `zpro001`), `llm_cost_log` (owned by `ze-core`, `zc` chain — read-only for
this feature, no schema change).

**Testing**: pytest, `asyncio_mode = "auto"`. Mock asyncpg pools with `AsyncMock` — no
real DB in unit tests. Mock `LLMClient`/`OpenRouterClient` — no real LLM calls.
`make test-core`, `make test-proactive`, `make test-worldstate`, `make test-api`.

**Target Platform**: Linux server (ze-api), single always-on process today; the
`push_log` fix must not assume single-process (per spec Assumptions).

**Project Type**: Backend feature spanning three existing packages
(`core/ze-core`, `core/ze-proactive` unaffected schema-wise but read by
`core/ze-worldstate`, `apps/ze-api`) — no new package.

**Performance Goals**: N/A (correctness/reliability fixes, not throughput-sensitive).
The budget check adds one extra async read per `capability_check` invocation; must stay
well under the existing per-turn LLM latency (no measurable UX regression).

**Constraints**: No new graph nodes (constitution favors minimal surface area;
`capability_check` already exists and is the natural extension point). No new external
API calls for the budget check — token-estimated cost only, consistent with the
existing `context_windows.py` static-table precedent (Phase 112), not a live
OpenRouter pricing lookup.

**Scale/Scope**: Single-user system (constitution II) — no per-user scoping anywhere in
this feature. Budget scope is per-session and per-day for the one user.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First Development** — PASS. Spec exists at `specs/phases/113-hardening-sweep/spec.md`; this plan and its artifacts precede implementation.
- **II. Single-User Model** — PASS. No `user_id` column or per-user scoping introduced anywhere (`pending_confirmations` stays keyed by conversation identity, not user; budget is a single global/per-session config value, not per-user).
- **III. Layered Package Architecture** — PASS. All three fixes stay inside their owning package: confirmation store + capability gate stay in `ze-core`; push_log store stays in `ze-proactive`; `ze-worldstate`'s `LoopSurfacer`/`PushSweepJob` (already depends on `ze-proactive`) only calls the store's existing/extended interface. No plugin touches `ze_core.*` or `ze_plugin.*` directly. No new core-owned closed enum is introduced for plugin-domain values — the budget-exceeded path reuses the existing `GateDecision` enum, which is already core-owned and doctrine-mandated (capability gating), not a new plugin-vocabulary leak.
- **IV. Typed, Explicit Python** — PASS. New pricing table follows the `context_windows.py` dataclass-free static-dict precedent; new config surface is a dataclass on `Settings`, not a raw dict; all I/O stays async; no bare `Exception`/`ValueError` planned — existing typed-error conventions in each touched module are preserved.
- **V. Test Discipline** — PASS (planned). Each of the three fixes gets tests in the owning package's `tests/` dir; concurrency scenarios are simulated with mocked stores (no real DB), consistent with existing `AsyncMock` conventions already used in `core/ze-worldstate/tests/jobs/test_push_sweep.py` and `core/ze-core/tests/capability/test_gate.py`.
- **VI. Explicit Persistence** — PASS. Two hand-written raw-SQL Alembic migrations planned: one on the `zc` chain (rekey `pending_confirmations`), one on the `zpro` chain (uniqueness on `push_log`). No ORM used.
- **VII. One LLM Gateway, Local Embeddings** — PASS. No new LLM or embedding calls introduced; the budget check is a static-table token estimate, not a live pricing API call.

No violations. Complexity Tracking section not needed.

## Project Structure

### Documentation (this feature)

```text
specs/phases/113-hardening-sweep/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/             # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
core/ze-core/ze_core/
├── conversation/confirmations/
│   └── store.py                      # PendingConfirmationStore — rekey save/get/clear to request_id
├── migrations/versions/
│   └── zc0XX_confirmations_request_id_key.py   # rekey pending_confirmations PK
├── capability/
│   └── gate.py                       # CapabilityGate — unchanged signature; budget check composed in the node, not the gate
├── telemetry/
│   ├── pricing.py                    # NEW — static per-model $/token table, mirrors openrouter/context_windows.py
│   └── budget.py                     # NEW — SpendBudgetChecker: running-total query + against-config comparison
└── orchestration/nodes/
    └── execution.py                  # capability_check — compose CapabilityGate decision with SpendBudgetChecker decision

apps/ze-api/ze_api/
├── api/websocket/
│   ├── endpoint.py                   # pending_configs dict rekeyed thread_id -> request_id (nested or composite key)
│   ├── confirmation.py               # handle_confirm/confirmation_timeout take request_id, not just thread_id
│   └── connection.py                 # ConnectionManager: no PK-shaped change expected, verify during implementation
└── config/config.yaml                # NEW `budget:` block (opt-in, absent = unchanged behavior)

core/ze-proactive/ze_proactive/
├── push_log_store.py                 # log() gains idempotency-key path; new claim-then-write or unique-violation-safe method
└── migrations/versions/
    └── zproXXX_push_log_idempotency.py   # unique constraint/index enforcing at-most-one push per (event_type, idempotency key)

core/ze-worldstate/ze_worldstate/
├── surfacing.py                      # LoopSurfacer.log_push — pass idempotency key (loop_id) through to the store
└── jobs/push_sweep.py                # PushSweepJob.run — treat a "already claimed" result from log_push as a skip, not an error
```

**Structure Decision**: No new package. Three narrow, package-local changes layered on
existing modules, following the dependency graph already documented in `CLAUDE.md`
(`ze-worldstate → ze-proactive`, `ze-api → ze-core`). `ze-core/telemetry/budget.py` is
new but sits in the existing `telemetry` subpackage rather than a new one, since it
reads from the same `CostStore`/`llm_cost_log` this subpackage already owns.

## Complexity Tracking

*No Constitution Check violations — section not needed.*
